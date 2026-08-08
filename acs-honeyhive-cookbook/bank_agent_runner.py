"""Drive Microsoft's bank_agent ACS policy through all 8 intervention points and
emit every runtime decision as a HoneyHive span.

This is the runtime-governance half of Microsoft's open trust stack:

    evaluate (ASSERT)  ->  enforce (ACS)  ->  observe (HoneyHive)

It loads the official bank_agent Rego policy + manifest (adapted only to supply a
custom, offline annotator dispatcher), runs the REAL ACS runtime
(``AgentControl.from_path`` against ``policy/bank_agent_rego.rego`` + OPA), and
feeds each intervention point its host snapshot. ``instrument_acs`` makes every
evaluation show up inline in the same HoneyHive trace as the agent's own model
call.

Usage:

    export ACS_OPA_PATH=/path/to/opa
    export HH_API_KEY=...        # HoneyHive
    export OPENAI_API_KEY=...    # optional; enables a real inline model-call span
    python bank_agent_runner.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from agent_control_specification import (
    AgentControl,
    Decision,
    EnforcementMode,
    InterventionPoint,
)
from honeyhive import HoneyHiveTracer, atrace, enrich_span, trace

from acs_honeyhive import instrument_acs
from bank_agent.annotators import BankClassifierAnnotator

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "bank_agent" / "manifest.yaml"
SNAPSHOTS = HERE / "bank_agent" / "snapshots"

SOURCE = "acs-bank-demo"
SESSION_NAME = "acs-bank-agent"

# Each intervention point, in agent-loop order, paired with the snapshot that
# exercises its interesting (non-default) branch so the full decision matrix
# (allow / deny / escalate / transform / warn) is demonstrated in one run.
INTERVENTION_SEQUENCE: list[tuple[InterventionPoint, str]] = [
    (InterventionPoint.AGENT_STARTUP, "agent_startup.json"),
    (InterventionPoint.INPUT, "input.json"),
    (InterventionPoint.PRE_MODEL_CALL, "pre_model_call.json"),
    (InterventionPoint.POST_MODEL_CALL, "post_model_call.json"),
    (InterventionPoint.PRE_TOOL_CALL, "pre_tool_call.json"),
    (InterventionPoint.POST_TOOL_CALL, "post_tool_call.json"),
    (InterventionPoint.OUTPUT, "output.json"),
    (InterventionPoint.AGENT_SHUTDOWN, "agent_shutdown.json"),
]


def _load_snapshot(filename: str) -> dict[str, Any]:
    return json.loads((SNAPSHOTS / filename).read_text())


def human_approval_callback(intervention_point: InterventionPoint, result: Any) -> bool:
    """Stub human-approval path for ``escalate`` verdicts. Rejects by default.

    A real host would suspend the action and consult a human or external
    authority. Returning ``False`` here keeps the demo non-interactive and
    deterministic: the escalated action is not approved.
    """
    return False


def _host_action(intervention_point: InterventionPoint, result: Any) -> str:
    """Apply the ACS-prescribed host action and return a human-readable summary.

    | Decision  | Host action                                            |
    |-----------|--------------------------------------------------------|
    | allow     | proceed unchanged                                      |
    | warn      | proceed, record warning                                |
    | deny      | block; surface reason + message                        |
    | escalate  | suspend; consult approval path before proceeding       |
    | transform | proceed only with the transformed policy target        |
    """
    verdict = result.verdict
    decision = verdict.decision
    if decision == Decision.ALLOW:
        return "proceed (allowed)"
    if decision == Decision.WARN:
        return f"proceed, warning recorded: {verdict.message}"
    if decision == Decision.DENY:
        return f"BLOCKED [{verdict.reason}]: {verdict.message}"
    if decision == Decision.ESCALATE:
        approved = human_approval_callback(intervention_point, result)
        return (
            "approved by human reviewer; proceed"
            if approved
            else f"SUSPENDED [{verdict.reason}] -> approval denied: {verdict.message}"
        )
    if decision == Decision.TRANSFORM:
        return f"proceed with transformed policy target: {result.transformed_policy_target!r}"
    # Exhaustive over Decision; a new variant should surface loudly.
    raise ValueError(f"Unhandled ACS decision: {decision!r}")


@trace(event_type="model", event_name="agent.model_call")
def agent_model_call(prompt: str) -> str:
    """A real (optional) agent model call, traced inline next to the ACS spans.

    Demonstrates that ACS governance spans and the agent's own model spans share
    one HoneyHive trace. Skipped gracefully if no OpenAI key is configured.
    """
    if not os.getenv("OPENAI_API_KEY"):
        enrich_span(outputs={"skipped": "no OPENAI_API_KEY"})
        return "(model call skipped: no OPENAI_API_KEY)"
    from openai import OpenAI

    client = OpenAI()
    response = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        messages=[
            {"role": "system", "content": "You are a careful bank assistant. Never bypass approvals."},
            {"role": "user", "content": prompt},
        ],
        max_tokens=120,
    )
    return response.choices[0].message.content or ""


@atrace(event_type="chain", event_name="governed_bank_turn")
async def governed_bank_turn(control: AgentControl) -> list[dict[str, Any]]:
    """Run one governed agent turn: every ACS point + a real model call, one trace."""
    summary: list[dict[str, Any]] = []

    # The agent's own model call, governed-in-spirit and traced inline.
    model_text = agent_model_call(
        "A customer asked to move $25,000 from checking to brokerage. What is the safe next step?"
    )
    print(f"\n[agent.model_call] -> {model_text[:120]!r}\n")

    for intervention_point, snapshot_file in INTERVENTION_SEQUENCE:
        snapshot = _load_snapshot(snapshot_file)
        # Patched by instrument_acs(): this emits a HoneyHive span automatically.
        result = await control.evaluate_intervention_point(
            intervention_point, snapshot, EnforcementMode.ENFORCE
        )
        action = _host_action(intervention_point, result)
        decision = result.verdict.decision.value
        print(f"  {intervention_point.value:16s} -> {decision:9s} | {action}")
        summary.append(
            {
                "intervention_point": intervention_point.value,
                "decision": decision,
                "reason": result.verdict.reason,
                "host_action": action,
            }
        )
    return summary


async def main() -> int:
    load_dotenv(override=True)

    if not os.getenv("HH_API_KEY"):
        print("ERROR: HH_API_KEY is not set. Add it to your environment or .env file.", file=sys.stderr)
        return 2
    if not os.getenv("ACS_OPA_PATH"):
        print(
            "ERROR: ACS_OPA_PATH is not set. ACS needs the OPA binary to evaluate Rego.\n"
            "       See scripts/setup_opa.sh and the README OPA setup note.",
            file=sys.stderr,
        )
        return 2

    tracer = HoneyHiveTracer.init(
        api_key=os.getenv("HH_API_KEY"),
        source=SOURCE,
        session_name=SESSION_NAME,
    )

    # Auto-instrument OpenAI so the agent's model call is traced (best-effort).
    try:
        from openinference.instrumentation.openai import OpenAIInstrumentor

        OpenAIInstrumentor().instrument(tracer_provider=tracer.provider)
    except Exception as exc:  # noqa: BLE001 - instrumentation is optional for the demo
        print(f"(OpenAI auto-instrumentation unavailable: {exc})")

    # The one line that captures ALL ACS activity as HoneyHive spans.
    instrument_acs(tracer)

    # Real ACS runtime: official Rego policy + OPA + a custom offline annotator
    # dispatcher so the annotation-gated points (input, pre_model_call) fire.
    control = AgentControl.from_path(
        str(MANIFEST),
        annotator_dispatcher=BankClassifierAnnotator(),
    )

    print("=" * 72)
    print("ACS x HoneyHive: governing the bank_agent through all 8 ACS points")
    print("=" * 72)
    print(f"manifest      : {MANIFEST}")
    print(f"opa           : {os.getenv('ACS_OPA_PATH')}")
    print(f"hh source     : {SOURCE}")
    print(f"hh session    : {SESSION_NAME}")
    print("-" * 72)

    summary = await governed_bank_turn(control)

    HoneyHiveTracer.flush_all()

    decisions = sorted({row["decision"] for row in summary})
    print("-" * 72)
    print("Run summary:")
    for row in summary:
        print(f"  {row['intervention_point']:16s} {row['decision']:9s} {row['reason'] or ''}")
    print("-" * 72)
    print(f"Decision types observed: {', '.join(decisions)}")
    print(f"Flushed {len(summary)} ACS spans to HoneyHive.")
    print(f"Find the trace in HoneyHive by source='{SOURCE}', session_name='{SESSION_NAME}'.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
