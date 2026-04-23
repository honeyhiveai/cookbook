"""Strands agent on Lambda, traced via HoneyHive.

Three patterns matter here; a reader poking at this later should know why:

1. HoneyHive tracer + Strands agent are built at module import time so the cost
   amortizes across Lambda container reuse. A warm invocation skips this entirely.
2. `MODEL_ARN` is fed straight to `BedrockModel(model_id=...)`. Bedrock's
   `converse()` accepts foundation-model IDs, regular inference-profile ARNs,
   and application-inference-profile ARNs interchangeably, so one code path
   handles all three shapes.
3. Per-invocation state must be reset — two things bleed across container reuse
   if you're not careful:
   (a) session id: use `tracer.with_session()` (OTEL baggage, ContextVar-based,
       auto-cleanup on scope exit), NOT `session_start()` which stores on the
       tracer singleton. This is the rc10 fix from customer-nationwide
       2025-10-28.
   (b) agent conversation history: the Strands `Agent` accumulates user and
       assistant turns in `self.messages`. Since `_agent` is the same singleton
       across warm invocations, invocation N would otherwise see the full
       history from invocations 1..N-1 — a privacy leak and an ever-growing
       token bill. Clear `_agent.messages` at the start of each invocation.
"""

from __future__ import annotations

import os
import uuid

from honeyhive import HoneyHiveTracer
from strands import Agent, tool
from strands.models.bedrock import BedrockModel

MODEL_ARN = os.environ.get("MODEL_ARN")
HONEYHIVE_API_KEY = os.environ.get("HONEYHIVE_API_KEY")
HONEYHIVE_PROJECT = os.environ.get("HONEYHIVE_PROJECT")
HONEYHIVE_SERVER_URL = os.environ.get("HONEYHIVE_SERVER_URL")
HONEYHIVE_APP_URL = os.environ.get("HONEYHIVE_APP_URL", "https://app.honeyhive.ai")

_INIT_ERROR: str | None = None
_tracer: HoneyHiveTracer | None = None
_agent: Agent | None = None


@tool
def calculator(expression: str) -> str:
    """Evaluate a simple arithmetic expression. Exists so the trace shows an agent->tool span."""
    allowed = set("0123456789+-*/(). ")
    if not expression or set(expression) - allowed:
        return "error: only digits and + - * / ( ) . are allowed"
    # Reject `**` — the char allowlist permits `*`, so `9**9**9` would slip through
    # and exhaust CPU/memory inside eval. Demo tool doesn't need exponentiation.
    if "**" in expression:
        return "error: exponentiation not allowed"
    try:
        return str(eval(expression, {"__builtins__": {}}, {}))  # noqa: S307 — input is whitelisted above
    except Exception as exc:
        return f"error: {exc}"


try:
    if not HONEYHIVE_API_KEY or not HONEYHIVE_PROJECT:
        raise RuntimeError("HONEYHIVE_API_KEY and HONEYHIVE_PROJECT must be set")
    if not MODEL_ARN:
        raise RuntimeError("MODEL_ARN must be set")

    tracer_kwargs = {"api_key": HONEYHIVE_API_KEY, "project": HONEYHIVE_PROJECT}
    if HONEYHIVE_SERVER_URL:
        tracer_kwargs["server_url"] = HONEYHIVE_SERVER_URL
    _tracer = HoneyHiveTracer.init(**tracer_kwargs)

    _agent = Agent(
        model=BedrockModel(model_id=MODEL_ARN),
        tools=[calculator],
        system_prompt="You are a concise assistant. Use the calculator tool for arithmetic.",
    )
except Exception as exc:
    _INIT_ERROR = f"{type(exc).__name__}: {exc}"


def handler(event, context):
    if _INIT_ERROR or _tracer is None or _agent is None:
        return {"error": "cold-start init failed", "detail": _INIT_ERROR}

    prompt = (event or {}).get("prompt") or "What is 17 * 23?"
    session_name = f"lambda-{uuid.uuid4().hex[:8]}"

    # Reset per-invocation agent state — see module docstring, item 3(b)
    _agent.messages.clear()

    try:
        with _tracer.with_session(
            session_name=session_name, inputs={"prompt": prompt}
        ) as session_id:
            result = _agent(prompt)
            response_text = str(result)
            _tracer.enrich_session(outputs={"response": response_text})
    except Exception as exc:
        return {
            "error": "agent invocation failed",
            "detail": f"{type(exc).__name__}: {exc}",
        }

    session_url = (
        f"{HONEYHIVE_APP_URL}/{HONEYHIVE_PROJECT}/sessions/{session_id}"
        if session_id
        else None
    )
    return {
        "response": response_text,
        "session_url": session_url,
        "session_id": session_id,
    }
