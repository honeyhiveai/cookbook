"""Strands agent on AWS Lambda, traced end-to-end with HoneyHive.

This file is a hands-on workshop example: parts of it are intentionally left as
``# TODO`` markers so a presenter can fill them in live with GitHub Copilot. The
surrounding context (imports, types, existing tools, comments) is the prompt
that primes Copilot to suggest the right next line.

Shape of an invocation::

    Lambda invoke
        -> HoneyHive session (via tracer.with_session)
            -> Strands Agent
                -> Bedrock model (converse)
                -> @tool calls (calculator, ...)

Environment variables (read once at module import):

    MODEL_ARN              Bedrock foundation-model id, inference-profile ARN, or
                           application-inference-profile ARN. Bedrock's
                           ``converse()`` accepts all three shapes interchangeably,
                           so one code path covers Claude / Nova / etc.
    HONEYHIVE_API_KEY      HoneyHive project API key.
    HONEYHIVE_PROJECT      HoneyHive project name.
    HONEYHIVE_SERVER_URL   Optional. Self-hosted HoneyHive ingest URL.
    HONEYHIVE_APP_URL      Optional. Used to build the session URL in the response
                           (defaults to ``https://app.honeyhive.ai``).

Returned JSON on success::

    {"response": str, "session_url": str | None, "session_id": str | None}

Returned JSON on failure::

    {"error": str, "detail": str}

Three patterns are pedagogically important — they are why the code is shaped
the way it is, and they are worth reading before editing:

1. **Cold-start init.** The tracer and agent are constructed at module import
   time, not inside ``handler``. Lambda reuses warm containers, so warm
   invocations skip init entirely and only pay for the agent call itself.
2. **Session id via baggage, not the tracer singleton.** ``tracer.with_session``
   stores ``session_id`` in OpenTelemetry baggage (a ContextVar that
   auto-cleans on scope exit). ``tracer.session_start`` would mutate the
   tracer singleton instead, which leaks the previous invocation's session_id
   into the next warm invocation. Always use ``with_session`` in Lambda.
3. **Per-invocation history reset.** Strands' ``Agent.messages`` accumulates
   user/assistant turns. Because ``_agent`` is a module-level singleton across
   warm invocations, invocation N would otherwise see the conversation from
   invocations 1..N-1 — a privacy leak and an ever-growing token bill. We
   clear ``_agent.messages`` at the top of every invocation.
"""

from __future__ import annotations

import os
import uuid
from typing import Any

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
    """Evaluates a simple arithmetic expression and returns the result as a string."""
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


# TODO: define a `current_time` @tool the agent can call. Mirror the calculator
# above: @tool decorator, one-line docstring, no arguments, returns a str. Use
# datetime.datetime.now(datetime.timezone.utc).isoformat() for an ISO-8601
# timestamp that's safe across Python runtimes.


try:
    if not HONEYHIVE_API_KEY or not HONEYHIVE_PROJECT:
        raise RuntimeError("HONEYHIVE_API_KEY and HONEYHIVE_PROJECT must be set")
    if not MODEL_ARN:
        raise RuntimeError("MODEL_ARN must be set")

    tracer_kwargs: dict[str, Any] = {
        "api_key": HONEYHIVE_API_KEY,
        "project": HONEYHIVE_PROJECT,
    }
    if HONEYHIVE_SERVER_URL:
        tracer_kwargs["server_url"] = HONEYHIVE_SERVER_URL
    _tracer = HoneyHiveTracer.init(**tracer_kwargs)

    _agent = Agent(
        model=BedrockModel(model_id=MODEL_ARN),
        # TODO: once `current_time` is defined above, register it here so the
        # agent can pick it. Tools are passed as a list of @tool-decorated
        # callables, e.g. `tools=[calculator, current_time]`.
        tools=[calculator],
        system_prompt="You are a concise assistant. Use the calculator tool for arithmetic.",
    )
except Exception as exc:
    _INIT_ERROR = f"{type(exc).__name__}: {exc}"


def handler(event: dict[str, Any] | None, context: Any) -> dict[str, Any]:
    """Returns the agent's response to ``event['prompt']``, wrapped in a HoneyHive session."""
    if _INIT_ERROR or _tracer is None or _agent is None:
        return {"error": "cold-start init failed", "detail": _INIT_ERROR}

    prompt = (event or {}).get("prompt") or "What is 17 * 23?"
    session_name = f"lambda-{uuid.uuid4().hex[:8]}"

    # Clear per-invocation conversation history. Lambda reuses warm containers,
    # and Strands' Agent.messages would otherwise carry user/assistant turns
    # across invocations (privacy leak + ever-growing token bill).
    _agent.messages.clear()

    try:
        # tracer.with_session uses OTEL baggage (a ContextVar that auto-cleans
        # on scope exit), so session_id can't leak into the next warm
        # invocation. Don't replace this with tracer.session_start() — that
        # mutates the tracer singleton and bleeds across invocations.
        with _tracer.with_session(
            session_name=session_name, inputs={"prompt": prompt}
        ) as session_id:
            # TODO: enrich the session with a custom attribute pulled from
            # `event` (e.g. user_id) so the trace is filterable per-user in
            # the HoneyHive UI. Use _tracer.enrich_session(metadata={...}).
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
