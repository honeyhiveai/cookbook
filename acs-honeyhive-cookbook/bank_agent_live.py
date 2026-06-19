"""A REAL, lifelike OpenAI tool-calling banking agent governed by ACS.

Where ``bank_agent_runner.py`` replays Microsoft's static `bank_agent` snapshots
to prove decision coverage, this runner builds an actual agent loop:

  * a real ``AsyncOpenAI`` tool-calling model (multiple turns), and
  * real Python tools (``lookup_account``, ``wire_transfer``)

...all mediated by the SAME official `bank_agent` Rego policy. Every model and
tool boundary is wrapped with ACS's host orchestration helpers
(``control.run`` for input/output, ``control.run_tool`` for tools, and explicit
``pre_model_call`` / ``post_model_call`` evaluations). All of those funnel
through ``AgentControl.evaluate_intervention_point``, so ``instrument_acs``
auto-emits a HoneyHive span for each governance decision — interleaved with the
agent's real ``ChatCompletion`` spans in one trace.

The result is the lifelike view: a multi-step agent doing actual work, with ACS
`allow` / `transform` / `escalate` decisions appearing inline as it runs.

Usage:
    export ACS_OPA_PATH=/path/to/opa
    export HH_API_KEY=...
    export OPENAI_API_KEY=...
    python bank_agent_live.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import AsyncOpenAI

from agent_control_specification import (
    AgentControl,
    AgentControlBlocked,
    AgentControlInterruption,
    ApprovalOutcome,
    Decision,
    EnforcementMode,
    InterventionPoint,
)
from honeyhive import HoneyHiveTracer, atrace, enrich_span

from acs_honeyhive import instrument_acs
from bank_agent.annotators import BankClassifierAnnotator

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "bank_agent" / "manifest.yaml"

SOURCE = "acs-bank-live"
SESSION_NAME = "acs-bank-agent-live"
MAX_TURNS = 5

# Ambient snapshot context merged into every intervention-point evaluation, so
# the policy input mirrors the upstream bank_agent fixtures (actor/agent/session).
AMBIENT = {
    "actor": {"id": "customer-123", "risk_tier": "standard", "roles": ["customer"]},
    "agent": {
        "capabilities": ["balance_lookup", "wire_transfer"],
        "id": "bank-agent-instance-001",
        "mode": "production",
        "name": "bank-agent",
        "version": "1.0.0-demo",
    },
    "session": {"created_at": "2025-02-03T10:15:00Z", "id": "session-bank-live-001"},
}

SYSTEM_PROMPT = (
    "You are an automated bank payment-processing agent that executes approved work "
    "orders by calling tools. For a transfer work order: first call lookup_account on "
    "the source account to confirm funds, then call wire_transfer to move the money. "
    "Execute approved work orders directly by calling the tools; do not ask the human "
    "to re-confirm. When you report results, include the account number you looked up."
)

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "lookup_account",
            "description": "Look up balance and metadata for a bank account.",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {"type": "string", "description": "e.g. CHK-00112233"},
                    "fields": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["account_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "wire_transfer",
            "description": "Move money from one account to another.",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {"type": "number"},
                    "currency": {"type": "string"},
                    "from_account_id": {"type": "string"},
                    "to_account_id": {"type": "string"},
                },
                "required": ["amount", "from_account_id", "to_account_id"],
            },
        },
    },
]

# A tiny fake core-banking backend the real tools call.
_ACCOUNTS = {
    "CHK-00112233": {"available_balance": 482651.40, "currency": "USD", "customer_tier": "premier"},
}


def lookup_account(args: dict[str, Any]) -> dict[str, Any]:
    account_id = args.get("account_id", "")
    record = _ACCOUNTS.get(account_id, {"available_balance": 0.0, "currency": "USD"})
    return {"account_id": account_id, **record}


def wire_transfer(args: dict[str, Any]) -> dict[str, Any]:
    # Only reached if ACS pre_tool_call permits it (small transfers). Large
    # transfers escalate and are blocked before this runs.
    return {
        "status": "executed",
        "amount": args.get("amount"),
        "from_account_id": args.get("from_account_id"),
        "to_account_id": args.get("to_account_id"),
    }


REAL_TOOLS = {"lookup_account": lookup_account, "wire_transfer": wire_transfer}


async def reject_wire_escalations(intervention_point: InterventionPoint, result: Any) -> ApprovalOutcome:
    """Stub human-approval path for ``escalate`` verdicts. Rejects by default."""
    return ApprovalOutcome.DENY


@atrace(event_type="tool", event_name="acs.pre_model_call")
async def guarded_model_request(control: AgentControl, messages: list[dict[str, Any]], model: str) -> list[dict[str, Any]]:
    """Evaluate ``pre_model_call`` and return the (possibly transformed) messages."""
    snapshot = {
        **AMBIENT,
        "model_request": {
            "messages": messages,
            "model": model,
            "tools": [{"name": s["function"]["name"]} for s in TOOL_SCHEMAS],
        },
    }
    result = await control.evaluate_intervention_point(
        InterventionPoint.PRE_MODEL_CALL, snapshot, EnforcementMode.ENFORCE
    )
    if result.verdict.decision == Decision.TRANSFORM and result.transformed_policy_target:
        transformed = result.transformed_policy_target.get("messages")
        if isinstance(transformed, list):
            return transformed
    return messages


@atrace(event_type="tool", event_name="acs.post_model_call")
async def guarded_model_response(control: AgentControl, message: dict[str, Any]) -> None:
    """Evaluate ``post_model_call``; raises if the response is blocked."""
    snapshot = {**AMBIENT, "model_response": {"message": message}}
    result = await control.evaluate_intervention_point(
        InterventionPoint.POST_MODEL_CALL, snapshot, EnforcementMode.ENFORCE
    )
    await control.enforce(InterventionPoint.POST_MODEL_CALL, result, EnforcementMode.ENFORCE)


def _message_for_acs(assistant: Any) -> dict[str, Any]:
    """Shape the model reply the way the bank_agent post_model_call rule reads it."""
    payload: dict[str, Any] = {"role": assistant.role, "content": assistant.content or ""}
    if assistant.tool_calls:
        payload["tool_calls"] = [
            {"id": tc.id, "name": tc.function.name, "args": json.loads(tc.function.arguments or "{}")}
            for tc in assistant.tool_calls
        ]
    return payload


def _message_for_openai(assistant: Any) -> dict[str, Any]:
    """Re-serialize the model reply into OpenAI wire format for the next turn."""
    payload: dict[str, Any] = {"role": "assistant", "content": assistant.content or ""}
    if assistant.tool_calls:
        payload["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            }
            for tc in assistant.tool_calls
        ]
    return payload


@atrace(event_type="chain", event_name="governed_bank_agent_live")
async def run_live_agent(control: AgentControl, client: AsyncOpenAI, user_text: str) -> str:
    model = os.getenv("OPENAI_MODEL", "gpt-4o")
    print(f"\nUSER: {user_text}\n")

    # --- input intervention point ---
    input_result = await control.evaluate_intervention_point(
        InterventionPoint.INPUT, {**AMBIENT, "input": {"text": user_text}}, EnforcementMode.ENFORCE
    )
    if input_result.verdict.decision == Decision.DENY:
        print(f"  [input] DENY: {input_result.verdict.message}")
        return f"Request blocked at input: {input_result.verdict.message}"

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_text},
    ]

    for turn in range(MAX_TURNS):
        effective_messages = await guarded_model_request(control, messages, model)

        # Real, OpenInference-traced model call.
        response = await client.chat.completions.create(
            model=model, messages=effective_messages, tools=TOOL_SCHEMAS, max_tokens=400
        )
        assistant = response.choices[0].message
        tool_names = [tc.function.name for tc in assistant.tool_calls or []]
        print(f"  [model turn {turn + 1}] tool_calls={tool_names or 'none'}")

        try:
            await guarded_model_response(control, _message_for_acs(assistant))
        except AgentControlBlocked as blocked:
            print(f"  [post_model_call] DENY: {blocked.result.verdict.message}")
            return f"Model response blocked: {blocked.result.verdict.message}"

        messages.append(_message_for_openai(assistant))

        if not assistant.tool_calls:
            final_text = assistant.content or ""
            break

        # --- tool calls, each governed by pre/post tool-call intervention points ---
        for tool_call in assistant.tool_calls:
            name = tool_call.function.name
            args = json.loads(tool_call.function.arguments or "{}")
            real_tool = REAL_TOOLS.get(name)
            if real_tool is None:
                tool_output: Any = {"error": f"unknown tool {name}"}
            else:
                try:
                    tool_run = await control.run_tool(
                        name,
                        args,
                        lambda effective_args, _fn=real_tool: _fn(effective_args),
                        tool_call_id=tool_call.id,
                        snapshot=AMBIENT,
                        approval_resolver=reject_wire_escalations,
                    )
                    tool_output = tool_run.value
                    pre_decision = tool_run.pre_tool_call_result.verdict.decision.value
                    print(f"    [tool {name}] pre={pre_decision} -> {tool_output}")
                except AgentControlInterruption as interruption:
                    result = getattr(interruption, "result", None)
                    verdict = result.verdict if result is not None else None
                    msg = verdict.message if verdict is not None else str(interruption)
                    reason = verdict.reason if verdict is not None else None
                    tool_output = {"error": "blocked_by_policy", "reason": reason, "detail": msg}
                    print(f"    [tool {name}] BLOCKED by ACS [{reason}]: {msg}")

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(tool_output),
            })
    else:
        final_text = "I was unable to complete the request within the allowed number of steps."

    # --- output intervention point (redacts account numbers) ---
    output_result = await control.evaluate_intervention_point(
        InterventionPoint.OUTPUT, {**AMBIENT, "output": {"text": final_text}}, EnforcementMode.ENFORCE
    )
    if output_result.verdict.decision == Decision.TRANSFORM and output_result.transformed_policy_target:
        final_text = output_result.transformed_policy_target.get("text", final_text)
        print("  [output] transform applied (account numbers redacted)")

    enrich_span(outputs={"final_answer": final_text})
    return final_text


async def main() -> int:
    load_dotenv(override=True)
    for required in ("HH_API_KEY", "OPENAI_API_KEY", "ACS_OPA_PATH"):
        if not os.getenv(required):
            print(f"ERROR: {required} is not set.", file=sys.stderr)
            return 2

    tracer = HoneyHiveTracer.init(
        api_key=os.getenv("HH_API_KEY"), source=SOURCE, session_name=SESSION_NAME
    )
    try:
        from openinference.instrumentation.openai import OpenAIInstrumentor

        OpenAIInstrumentor().instrument(tracer_provider=tracer.provider)
    except Exception as exc:  # noqa: BLE001
        print(f"(OpenAI auto-instrumentation unavailable: {exc})")

    instrument_acs(tracer)

    control = AgentControl.from_path(str(MANIFEST), annotator_dispatcher=BankClassifierAnnotator())
    client = AsyncOpenAI()

    print("=" * 72)
    print("ACS x HoneyHive: a LIVE OpenAI banking agent under bank_agent governance")
    print("=" * 72)
    print(f"manifest   : {MANIFEST}")
    print(f"hh source  : {SOURCE}  | session: {SESSION_NAME}")

    answer = await run_live_agent(
        control,
        client,
        "WORK ORDER #4471 (approved): Transfer $25,000 from source account "
        "CHK-00112233 to brokerage account BRK-00445566. Confirm available funds "
        "first, then execute the wire.",
    )

    HoneyHiveTracer.flush_all()
    print("-" * 72)
    print(f"FINAL ANSWER: {answer}")
    print("-" * 72)
    print(f"Find the trace in HoneyHive by source='{SOURCE}', session_name='{SESSION_NAME}'.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
