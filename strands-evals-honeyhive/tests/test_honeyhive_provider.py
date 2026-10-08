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


def test_http_error_raises_provider_error() -> None:
    client = httpx.Client(
        base_url="https://api.example.test",
        transport=httpx.MockTransport(lambda request: httpx.Response(401, json={"message": "Unauthorized"})),
    )
    with pytest.raises(ProviderError):
        HoneyHiveProvider(api_key="bad", client=client).get_evaluation_data("any")
