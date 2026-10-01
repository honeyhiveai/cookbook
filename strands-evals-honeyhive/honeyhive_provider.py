"""HoneyHive trace provider for running Strands Evals evaluators on HoneyHive sessions."""

from __future__ import annotations

import json
import logging
import os
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, cast

import httpx
from strands_evals.providers.exceptions import ProviderError, SessionNotFoundError
from strands_evals.providers.trace_provider import TraceProvider
from strands_evals.types.evaluation import TaskOutput
from strands_evals.types.trace import (
    AgentInvocationSpan,
    AssistantMessage,
    InferenceSpan,
    Session,
    SpanInfo,
    TextContent,
    ToolCall,
    ToolCallContent,
    ToolConfig,
    ToolExecutionSpan,
    ToolResult,
    ToolResultContent,
    Trace,
    UserMessage,
)
from tenacity import Retrying, before_sleep_log, retry_if_exception_type, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

__all__ = ["HoneyHiveProvider"]

_DEFAULT_API_URL = "https://api.dp1.us.honeyhive.ai"
_DEFAULT_TIMEOUT = 60.0
# The search endpoint caps `limit` at 1000.
_PAGE_SIZE = 1000
_MAX_RETRIES = 3


class HoneyHiveProvider(TraceProvider):
    """Retrieves agent sessions from HoneyHive for evaluation.

    HoneyHive stores each OpenTelemetry span as an event in a session. This provider
    fetches a session's events with the HoneyHive events search API and converts the Strands
    spans (``invoke_agent``, ``chat``, ``execute_tool``) to Strands Evals span types.
    It works for agents written with the Strands Python SDK and the Strands TypeScript SDK.
    Use a HoneyHive project API key.

    Example::

        from strands_evals import Case, Experiment
        from strands_evals.evaluators import HelpfulnessEvaluator

        provider = HoneyHiveProvider()  # Reads HH_API_KEY
        case = Case(name="checkout-question", session_id="<honeyhive-session-id>", input="...")
        report = Experiment(cases=[case], evaluators=[HelpfulnessEvaluator()]).run_evaluations(
            provider.as_task()
        )
    """

    def __init__(
        self,
        api_key: str | None = None,
        api_url: str | None = None,
        timeout: float = _DEFAULT_TIMEOUT,
        client: httpx.Client | None = None,
    ):
        """Initialize the HoneyHive provider.

        Args:
            api_key: HoneyHive project API key. Falls back to the HH_API_KEY environment variable.
                Ignored when ``client`` is passed.
            api_url: HoneyHive data plane URL. Falls back to the HH_API_URL environment variable,
                then to the HoneyHive cloud URL.
            timeout: Request timeout in seconds.
            client: An httpx client to use instead of creating one. Tests use this to inject a
                mock transport.

        Raises:
            ProviderError: If no client is passed and no API key can be resolved.
        """
        if client is not None:
            self._client = client
            return
        resolved_key = api_key or os.environ.get("HH_API_KEY")
        if not resolved_key:
            raise ProviderError("HoneyHive API key required. Provide api_key or set HH_API_KEY.")
        resolved_url = (api_url or os.environ.get("HH_API_URL") or _DEFAULT_API_URL).rstrip("/")
        self._client = httpx.Client(
            base_url=resolved_url,
            headers={"Authorization": f"Bearer {resolved_key}"},
            timeout=timeout,
        )

    def get_evaluation_data(self, session_id: str) -> TaskOutput:
        """Fetch a HoneyHive session and return its final output and trajectory."""
        events = self._fetch_session_events(session_id)
        if not events:
            raise SessionNotFoundError(f"HoneyHive: no events found for session_id='{session_id}'")

        session = self._build_session(session_id, events)
        if not session.traces:
            raise SessionNotFoundError(
                f"HoneyHive: session_id='{session_id}' has events but none are Strands agent spans"
            )
        return TaskOutput(output=self._extract_output(session), trajectory=session)

    # --- Fetching ---

    def _fetch_session_events(self, session_id: str) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        page = 1
        while True:
            body = {
                "filters": [{"field": "session_id", "operator": "is", "value": session_id, "type": "string"}],
                "limit": _PAGE_SIZE,
                "page": page,
            }
            try:
                payload = self._post_with_retry("/v1/events/search", body)
            except (httpx.HTTPError, ValueError) as e:
                raise ProviderError(f"HoneyHive: failed to fetch events for session '{session_id}': {e}") from e
            batch = payload.get("events") or []
            events.extend(batch)
            if len(batch) < _PAGE_SIZE:
                return events
            page += 1

    def _post_with_retry(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        """POST and return the JSON body. Retries timeouts, which a large session can hit."""
        for attempt in Retrying(
            retry=retry_if_exception_type(httpx.TimeoutException),
            stop=stop_after_attempt(_MAX_RETRIES),
            wait=wait_exponential(multiplier=1, max=10),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        ):
            with attempt:
                response = self._client.post(path, json=body)
                response.raise_for_status()
                payload = response.json()
        if not isinstance(payload, dict):
            raise ProviderError(f"HoneyHive: expected a JSON object from {path}, got {type(payload).__name__}")
        return payload

    # --- Assembly ---

    def _build_session(self, session_id: str, events: list[dict[str, Any]]) -> Session:
        """Group events by OpenTelemetry trace ID and convert each one to a typed span.

        The session event itself carries no trace ID and is not a span, so it is skipped.
        Traces are ordered by their earliest span, and spans by start time.
        """
        by_trace: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for event in events:
            if event.get("event_type") == "session":
                continue
            trace_id = (event.get("metadata") or {}).get("trace_id") or session_id
            by_trace[trace_id].append(event)

        traces = []
        for trace_id, trace_events in by_trace.items():
            trace_events.sort(key=lambda e: e.get("start_time") or 0)
            spans = []
            for event in trace_events:
                try:
                    span = self._convert_event(event, session_id)
                # One malformed event must not drop the whole session. Pydantic's ValidationError
                # is a ValueError.
                except (AttributeError, KeyError, TypeError, ValueError) as e:
                    logger.warning("event_id=<%s>, error=<%s> | failed to convert event", event.get("event_id"), e)
                    continue
                if span is not None:
                    spans.append(span)
            if spans:
                traces.append(Trace(trace_id=trace_id, session_id=session_id, spans=spans))

        traces.sort(key=lambda t: t.spans[0].span_info.start_time)
        return Session(session_id=session_id, traces=traces)

    def _convert_event(self, event: dict[str, Any], session_id: str) -> Any:
        """Route a HoneyHive event to a span converter by its OpenTelemetry span name.

        Strands names its spans the same way in Python and TypeScript:

            invoke_agent <name>        → AgentInvocationSpan
            model event (``chat``)      → InferenceSpan
            execute_tool <name>        → ToolExecutionSpan

        Event loop cycle spans carry no information the evaluators use, so they are skipped.
        """
        name = event.get("event_name") or ""
        if name.startswith("invoke_agent"):
            return self._convert_agent_invocation(event, session_id)
        if name.startswith("execute_tool"):
            return self._convert_tool_execution(event, session_id)
        if event.get("event_type") == "model":
            return self._convert_inference(event, session_id)
        return None

    def _span_info(self, event: dict[str, Any], session_id: str) -> SpanInfo:
        metadata = event.get("metadata") or {}
        return SpanInfo(
            trace_id=metadata.get("trace_id"),
            span_id=metadata.get("span_id") or event.get("event_id"),
            session_id=session_id,
            parent_span_id=metadata.get("parent_span_id"),
            start_time=_to_datetime(event.get("start_time")),
            end_time=_to_datetime(event.get("end_time")),
        )

    # --- Converters ---

    def _convert_agent_invocation(self, event: dict[str, Any], session_id: str) -> AgentInvocationSpan:
        """Convert an ``invoke_agent`` event.

        inputs:  {"chat_history": [{"role": "user", "content": "What is 25 * 4?"}, ...]}
        outputs: {"content": "25 multiplied by 4 is 100."}
        config:  {"tools": ["calculator"], ...}
        """
        history = (event.get("inputs") or {}).get("chat_history") or []
        user_prompt = next(
            (_text_of(m.get("content")) for m in reversed(history) if m.get("role") == "user"),
            "",
        )
        tools = (event.get("config") or {}).get("tools") or []
        return AgentInvocationSpan(
            span_info=self._span_info(event, session_id),
            user_prompt=user_prompt,
            agent_response=_text_of((event.get("outputs") or {}).get("content")).strip(),
            available_tools=[ToolConfig(name=t) for t in tools if isinstance(t, str)],
            metadata=event.get("metadata") or {},
        )

    def _convert_inference(self, event: dict[str, Any], session_id: str) -> InferenceSpan:
        """Convert a model event. The completion is appended as the final assistant message."""
        history = (event.get("inputs") or {}).get("chat_history") or []
        messages = [m for m in (_convert_message(raw) for raw in history) if m is not None]
        outputs = event.get("outputs") or {}
        completion = _convert_message({"role": "assistant", "content": outputs.get("content")})
        if completion is not None:
            messages.append(completion)
        return InferenceSpan(
            span_info=self._span_info(event, session_id),
            messages=messages,
            metadata=event.get("metadata") or {},
        )

    def _convert_tool_execution(self, event: dict[str, Any], session_id: str) -> ToolExecutionSpan:
        """Convert an ``execute_tool`` event.

        inputs:  {"parameters": {"a": 25, "b": 4}}
        outputs: {"result": 100, "tool_call_id": "call_..."}
        config:  {"tool_name": "calculator", "tool_description": "..."}
        """
        config = event.get("config") or {}
        inputs = event.get("inputs") or {}
        outputs = event.get("outputs") or {}
        name = config.get("tool_name") or (event.get("event_name") or "").removeprefix("execute_tool").strip()
        arguments = inputs.get("parameters")
        result = outputs.get("result")
        tool_call_id = outputs.get("tool_call_id")
        return ToolExecutionSpan(
            span_info=self._span_info(event, session_id),
            tool_call=ToolCall(
                name=name,
                arguments=arguments if isinstance(arguments, dict) else {},
                tool_call_id=tool_call_id,
            ),
            tool_result=ToolResult(
                content=result if isinstance(result, str) else json.dumps(result),
                error=event.get("error") or None,
                tool_call_id=tool_call_id,
            ),
            metadata=event.get("metadata") or {},
        )

    def _extract_output(self, session: Session) -> str:
        """Return the last agent response in the session, or an empty string."""
        for trace in reversed(session.traces):
            for span in reversed(trace.spans):
                if isinstance(span, AgentInvocationSpan):
                    return span.agent_response
        return ""


# --- Message helpers ---


def _to_datetime(value: Any) -> datetime:
    """HoneyHive stores start and end times as Unix milliseconds.

    Raises ValueError for a missing time. _build_session then skips the event, because an
    invented time would put the span in the wrong place in the trajectory.
    """
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
    raise ValueError(f"invalid event time: {value!r}")


def _text_of(content: Any) -> str:
    """Flatten message content to text. Strands content is a string or a list of blocks."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(block.get("text", "") for block in content if isinstance(block, dict))
    if isinstance(content, dict):
        return str(content.get("text", ""))
    return str(content)


def _tool_use_of(block: dict[str, Any]) -> dict[str, Any] | None:
    """Return the tool call in a content block.

    Python Strands nests it as ``{"toolUse": {...}}``. TypeScript Strands can also flatten it
    to ``{"type": "toolUse", "name": ..., "input": ..., "toolUseId": ...}``.
    """
    if isinstance(block.get("toolUse"), dict):
        return cast(dict[str, Any], block["toolUse"])
    if block.get("type") == "toolUse":
        return block
    return None


def _convert_message(raw: dict[str, Any]) -> UserMessage | AssistantMessage | None:
    """Convert a Strands chat message to a Strands Evals message.

    Roles map as follows. ``system`` messages are dropped because Strands Evals messages
    have no system role.

        user       → UserMessage with text
        tool       → UserMessage with a tool result (Strands sends tool results as user turns)
        assistant  → AssistantMessage with text and tool calls
    """
    role = raw.get("role")
    content = raw.get("content")

    if role == "tool":
        result = _parse_tool_result(content)
        return UserMessage(content=[result]) if result is not None else None

    if role == "user":
        text = _text_of(content)
        return UserMessage(content=[TextContent(text=text)]) if text else None

    if role == "assistant":
        blocks: list[TextContent | ToolCallContent] = []
        if isinstance(content, str):
            content = _maybe_json_list(content)
        if isinstance(content, str):
            if content:
                blocks.append(TextContent(text=content))
        elif isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                tool_use = _tool_use_of(block)
                if tool_use is not None:
                    blocks.append(
                        ToolCallContent(
                            name=tool_use.get("name", ""),
                            arguments=tool_use.get("input") or {},
                            tool_call_id=tool_use.get("toolUseId"),
                        )
                    )
                elif block.get("text"):
                    blocks.append(TextContent(text=block["text"]))
        return AssistantMessage(content=blocks) if blocks else None

    return None


def _maybe_json_list(text: str) -> Any:
    """Parse assistant content that the exporter serialized to a JSON list of blocks."""
    stripped = text.strip()
    if stripped.startswith("[") and stripped.endswith("]"):
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            return text
    return text


def _parse_tool_result(content: Any) -> ToolResultContent | None:
    """Parse a tool message. Strands serializes it as ``{"toolResult": {...}}`` in a JSON string."""
    payload = content
    if isinstance(content, str):
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            return ToolResultContent(content=content)
    if not isinstance(payload, dict):
        return None
    result = payload.get("toolResult") or payload
    status = result.get("status")
    return ToolResultContent(
        content=_text_of(result.get("content")),
        error=None if status in (None, "success") else str(status),
        tool_call_id=result.get("toolUseId"),
    )
