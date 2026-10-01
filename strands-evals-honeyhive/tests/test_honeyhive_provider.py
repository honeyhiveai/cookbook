"""Tests for HoneyHiveProvider. They use recorded HoneyHive sessions and a mock HTTP transport."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from strands_evals.providers.exceptions import ProviderError, SessionNotFoundError
from strands_evals.types.trace import (
    AgentInvocationSpan,
    AssistantMessage,
    InferenceSpan,
    TextContent,
    ToolCallContent,
    ToolExecutionSpan,
    ToolResultContent,
    UserMessage,
)

from honeyhive_provider import HoneyHiveProvider

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> list[dict[str, Any]]:
    return json.loads((FIXTURES / name).read_text())["events"]


def _provider(events: list[dict[str, Any]], requests: list[dict[str, Any]] | None = None) -> HoneyHiveProvider:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if requests is not None:
            requests.append({"path": request.url.path, "body": body, "auth": request.headers["Authorization"]})
        page, limit = body["page"], body["limit"]
        return httpx.Response(200, json={"events": events[(page - 1) * limit : page * limit]})

    client = httpx.Client(
        base_url="https://api.example.test",
        headers={"Authorization": "Bearer test-key"},
        transport=httpx.MockTransport(handler),
    )
    return HoneyHiveProvider(api_key="test-key", client=client)


@pytest.mark.parametrize("fixture", ["strands_ts_session.json", "strands_py_session.json"])
def test_converts_strands_session(fixture: str) -> None:
    events = _load(fixture)
    session_id = next(e["session_id"] for e in events)

    data = _provider(events).get_evaluation_data(session_id)

    assert data["output"] == "25 multiplied by 4 is 100."
    session = data["trajectory"]
    assert session.session_id == session_id
    assert len(session.traces) == 1
    spans = session.traces[0].spans
    kinds = [type(s) for s in spans]
    assert kinds.count(AgentInvocationSpan) == 1
    assert kinds.count(InferenceSpan) == 2
    assert kinds.count(ToolExecutionSpan) == 1
    # The session event and event loop cycle spans are not evaluation spans.
    assert len(spans) == 4
    assert [s.span_info.start_time for s in spans] == sorted(s.span_info.start_time for s in spans)


@pytest.mark.parametrize("fixture", ["strands_ts_session.json", "strands_py_session.json"])
def test_agent_invocation_fields(fixture: str) -> None:
    events = _load(fixture)
    data = _provider(events).get_evaluation_data(events[0]["session_id"])
    agent = next(s for s in data["trajectory"].traces[0].spans if isinstance(s, AgentInvocationSpan))

    assert agent.user_prompt == "What is 25 * 4?"
    assert agent.agent_response == "25 multiplied by 4 is 100."
    assert [t.name for t in agent.available_tools] == ["calculator"]


@pytest.mark.parametrize("fixture", ["strands_ts_session.json", "strands_py_session.json"])
def test_tool_execution_fields(fixture: str) -> None:
    events = _load(fixture)
    data = _provider(events).get_evaluation_data(events[0]["session_id"])
    tool = next(s for s in data["trajectory"].traces[0].spans if isinstance(s, ToolExecutionSpan))

    assert tool.tool_call.name == "calculator"
    assert tool.tool_call.arguments == {"a": 25, "b": 4}
    assert tool.tool_call.tool_call_id is not None
    assert tool.tool_result.tool_call_id == tool.tool_call.tool_call_id
    assert float(tool.tool_result.content) == 100


@pytest.mark.parametrize("fixture", ["strands_ts_session.json", "strands_py_session.json"])
def test_inference_messages_include_tool_round_trip(fixture: str) -> None:
    events = _load(fixture)
    data = _provider(events).get_evaluation_data(events[0]["session_id"])
    inferences = [s for s in data["trajectory"].traces[0].spans if isinstance(s, InferenceSpan)]
    first, second = inferences

    # First call: the user asks, and the model's completion is a tool call.
    assert isinstance(first.messages[0], UserMessage)
    assert first.messages[0].content == [TextContent(text="What is 25 * 4?")]
    assert isinstance(first.messages[-1], AssistantMessage)
    call = first.messages[-1].content[0]
    assert isinstance(call, ToolCallContent)
    assert call.name == "calculator"
    assert call.arguments == {"a": 25, "b": 4}

    # Second call: the tool result comes back as a user turn, and the completion is text.
    roles = [type(m) for m in second.messages]
    assert roles == [UserMessage, AssistantMessage, UserMessage, AssistantMessage]
    result = second.messages[2].content[0]
    assert isinstance(result, ToolResultContent)
    assert result.tool_call_id == call.tool_call_id
    assert result.error is None
    assert second.messages[-1].content == [TextContent(text="25 multiplied by 4 is 100.")]


def test_requests_session_events_with_filter() -> None:
    events = _load("strands_ts_session.json")
    requests: list[dict[str, Any]] = []
    session_id = events[0]["session_id"]

    _provider(events, requests).get_evaluation_data(session_id)

    assert requests[0]["path"] == "/v1/events/export"
    assert requests[0]["auth"] == "Bearer test-key"
    assert requests[0]["body"]["filters"] == [
        {"field": "session_id", "operator": "is", "value": session_id, "type": "string"}
    ]


def test_paginates_until_short_page(monkeypatch: pytest.MonkeyPatch) -> None:
    import honeyhive_provider

    monkeypatch.setattr(honeyhive_provider, "_PAGE_SIZE", 3)
    events = _load("strands_ts_session.json")
    requests: list[dict[str, Any]] = []

    data = _provider(events, requests).get_evaluation_data(events[0]["session_id"])

    assert [r["body"]["page"] for r in requests] == [1, 2, 3]
    assert len(data["trajectory"].traces[0].spans) == 4


def test_missing_session_raises() -> None:
    with pytest.raises(SessionNotFoundError):
        _provider([]).get_evaluation_data("00000000-0000-0000-0000-000000000000")


def test_session_without_strands_spans_raises() -> None:
    events = [e for e in _load("strands_ts_session.json") if e["event_type"] == "session"]
    with pytest.raises(SessionNotFoundError):
        _provider(events).get_evaluation_data(events[0]["session_id"])


def test_http_error_raises_provider_error() -> None:
    client = httpx.Client(
        base_url="https://api.example.test",
        transport=httpx.MockTransport(lambda request: httpx.Response(401, json={"message": "Unauthorized"})),
    )
    with pytest.raises(ProviderError):
        HoneyHiveProvider(api_key="bad", client=client).get_evaluation_data("any")


def test_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HH_API_KEY", raising=False)
    with pytest.raises(ProviderError):
        HoneyHiveProvider()


def test_malformed_event_is_skipped() -> None:
    events = _load("strands_ts_session.json")
    tool = next(e for e in events if e["event_name"].startswith("execute_tool"))
    tool["inputs"] = "not a dict"

    data = _provider(events).get_evaluation_data(events[0]["session_id"])

    spans = data["trajectory"].traces[0].spans
    assert not any(isinstance(s, ToolExecutionSpan) for s in spans)
    assert len(spans) == 3
