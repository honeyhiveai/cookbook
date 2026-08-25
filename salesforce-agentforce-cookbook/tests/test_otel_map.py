"""Behavior specs for public session grouping and span kind."""

from __future__ import annotations

import unittest
import uuid

from otel_map import (
    honeyhive_session_id,
    openinference_span_kind,
    stamp_and_map,
)


class SessionIdTest(unittest.TestCase):
    def test_uuid_passthrough(self) -> None:
        sid = "5fd03ee0-c76d-4d57-9ed4-d43556ab8e73"
        self.assertEqual(honeyhive_session_id(sid), sid)

    def test_non_uuid_is_stable_uuid5(self) -> None:
        sid = "not-a-uuid"
        expected = str(uuid.uuid5(uuid.NAMESPACE_URL, f"agentforce:{sid}"))
        self.assertEqual(honeyhive_session_id(sid), expected)


class SpanKindTest(unittest.TestCase):
    def test_llm_step_is_llm(self) -> None:
        self.assertEqual(
            openinference_span_kind({"name": "chat"}, {"step.type": "LLM_STEP"}),
            "LLM",
        )

    def test_state_update_is_tool(self) -> None:
        self.assertEqual(
            openinference_span_kind(
                {"name": "__state_update_action__"}, {"step.type": "VARIABLE_UPDATE_STEP"}
            ),
            "TOOL",
        )

    def test_turn_is_chain(self) -> None:
        self.assertEqual(
            openinference_span_kind({"name": "GeneralFAQ"}, {}),
            "CHAIN",
        )


class StampTest(unittest.TestCase):
    def test_stamps_public_session_and_kind_only(self) -> None:
        payload = {
            "resourceSpans": [
                {
                    "resource": {"attributes": []},
                    "scopeSpans": [
                        {
                            "spans": [
                                {
                                    "name": "chat",
                                    "attributes": [
                                        {
                                            "key": "step.type",
                                            "value": {"stringValue": "LLM_STEP"},
                                        },
                                        {
                                            "key": "gen_ai.request.model",
                                            "value": {"stringValue": "gpt-4o"},
                                        },
                                    ],
                                }
                            ]
                        }
                    ],
                }
            ]
        }
        stamp_and_map(payload, "5fd03ee0-c76d-4d57-9ed4-d43556ab8e73", "DemoAgent")
        resource_keys = {
            item["key"]
            for item in payload["resourceSpans"][0]["resource"]["attributes"]
        }
        span_attrs = {
            item["key"]: item["value"]
            for item in payload["resourceSpans"][0]["scopeSpans"][0]["spans"][0][
                "attributes"
            ]
        }
        self.assertIn("honeyhive.session_id", resource_keys)
        self.assertIn("gen_ai.conversation.id", resource_keys)
        self.assertIn("gen_ai.agent.name", resource_keys)
        self.assertEqual(span_attrs["openinference.span.kind"]["stringValue"], "LLM")
        self.assertEqual(
            span_attrs["gen_ai.request.model"]["stringValue"], "gpt-4o"
        )
        self.assertNotIn("honeyhive_event_type", span_attrs)
        self.assertFalse(
            any(key.startswith("honeyhive_inputs") for key in span_attrs)
        )


if __name__ == "__main__":
    unittest.main()
