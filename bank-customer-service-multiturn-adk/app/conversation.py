"""Shared session + turn-running logic for the server and the scenario script.

Kept in one place because the event-parsing here is the part most likely to be
written wrong: a single tool-calling turn yields three events, and parts[0].text
is None on the first two.
"""

# Telemetry must be initialized before ADK is imported anywhere.
from app.telemetry import get_tracer  # isort:skip

_TRACER = get_tracer()

import logging
import uuid

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from app import db
from app.agent import build_agent

logger = logging.getLogger(__name__)

APP_NAME = "bank_cs"

_session_service = InMemorySessionService()
_runner = Runner(
    app_name=APP_NAME, agent=build_agent(), session_service=_session_service
)

# session_id -> customer_id, so /api/chat knows who is authenticated
_sessions: dict[str, str] = {}

# session_id -> running transcript. The session event's own inputs/outputs arrive
# EMPTY from the instrumentation — the conversation lives on child spans — so the
# session-level LLM judge has nothing to read unless we put it there ourselves.
_transcripts: dict[str, list[str]] = {}


async def create_chat_session(customer_id: str) -> dict:
    """Create a HoneyHive session and an ADK session that share one id."""
    record = db.get_customer(customer_id)
    if not record:
        raise ValueError(f"Unknown customer {customer_id}")
    customer_id = record["customer_id"]

    session_id = None
    if _TRACER is not None:
        # Stores the id in OTel baggage (ContextVar-based), so this is safe under
        # concurrent requests. Never mutate tracer.session_id per request.
        session_id = _TRACER.create_session(
            session_name=f"chat-{customer_id}",
            user_properties={"user_id": customer_id},
            metadata={
                "authenticated_customer_id": customer_id,
                "channel": "web",
            },
        )

    if not session_id:
        session_id = str(uuid.uuid4())

    await _session_service.create_session(
        app_name=APP_NAME,
        user_id=customer_id,
        session_id=session_id,
        state={"authenticated_customer_id": customer_id},
    )

    _sessions[session_id] = customer_id
    return {
        "session_id": session_id,
        "customer_id": customer_id,
        "display_name": record["profile"]["full_name"],
    }


def _summarize(value, limit: int = 240) -> str:
    text = str(value)
    return text if len(text) <= limit else text[: limit - 1] + "…"


async def run_turn(session_id: str, message: str) -> dict:
    """Run one user turn. Returns {reply, tool_calls}."""
    customer_id = _sessions.get(session_id)
    if customer_id is None:
        raise KeyError(f"Unknown session {session_id}")

    reply_parts: list[str] = []
    tool_calls: list[dict] = []
    responses: dict[str, object] = {}

    async for event in _runner.run_async(
        user_id=customer_id,
        session_id=session_id,
        new_message=types.Content(role="user", parts=[types.Part(text=message)]),
    ):
        if not (event.content and event.content.parts):
            continue

        for part in event.content.parts:
            if getattr(part, "function_call", None):
                fc = part.function_call
                tool_calls.append({"name": fc.name, "args": dict(fc.args or {})})
            if getattr(part, "function_response", None):
                fr = part.function_response
                responses[fr.name] = fr.response

        # parts[0].text is None on function_call / function_response events
        text = "".join(p.text for p in event.content.parts if p.text)
        if text:
            reply_parts.append(text)

    for call in tool_calls:
        if call["name"] in responses:
            call["result_summary"] = _summarize(responses[call["name"]])

    reply = "".join(reply_parts).strip()

    # Keep the session event's inputs/outputs in step with the conversation so the
    # session-level judge can actually read it. Only user and assistant text goes
    # in: the judge's question is what the ASSISTANT disclosed, and feeding it raw
    # tool output would make it score data the assistant may have refused to share.
    turns = _transcripts.setdefault(session_id, [])
    turns.append(f"user: {message}")
    turns.append(f"assistant: {reply}")

    if _TRACER is not None:
        try:
            _TRACER.enrich_session(
                session_id=session_id,
                inputs={"conversation": "\n\n".join(turns)},
                outputs={"final_response": reply},
            )
        except Exception:
            logger.debug("enrich_session failed", exc_info=True)

    return {
        "reply": reply,
        "tool_calls": tool_calls,
    }


def finalize_session(session_id: str) -> bool:
    """Write the complete transcript to the session event.

    Call this AFTER flushing spans. The backend recomputes session metadata
    (num_events, cost, token counts) as spans arrive, which can overwrite an
    enrichment written before the flush — so the last word has to come last.
    """
    turns = _transcripts.get(session_id)
    if not turns or _TRACER is None:
        return False
    try:
        _TRACER.enrich_session(
            session_id=session_id,
            inputs={"conversation": "\n\n".join(turns)},
            outputs={"final_response": turns[-1].removeprefix("assistant: ")},
        )
        return True
    except Exception:
        logger.debug("finalize_session failed", exc_info=True)
        return False


def drop_session(session_id: str) -> bool:
    _transcripts.pop(session_id, None)
    return _sessions.pop(session_id, None) is not None
