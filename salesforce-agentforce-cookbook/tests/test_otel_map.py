"""Behavior specs for public session grouping, GenAI I/O rewrite, and operation name."""

from __future__ import annotations

import json
import unittest
import uuid

from otel_map import (
    attr,
    honeyhive_session_id,
    operation_name,
    span_kind,
    stamp_and_map,
)


def _span_attr_strings(payload: dict) -> dict:
    return {
        item["key"]: item["value"].get("stringValue")
        for item in payload["resourceSpans"][0]["scopeSpans"][0]["spans"][0]["attributes"]
        if "stringValue" in (item.get("value") or {})
    }


def _payload(name: str, attributes: list) -> dict:
    return {
        "resourceSpans": [
            {
                "resource": {"attributes": []},
                "scopeSpans": [{"spans": [{"name": name, "attributes": attributes}]}],
            }
        ]
    }


class SessionIdTest(unittest.TestCase):
    def test_salesforce_uuid_is_not_reused(self) -> None:
        sid = "5fd03ee0-c76d-4d57-9ed4-d43556ab8e73"
        derived = honeyhive_session_id(sid)
        self.assertNotEqual(derived, sid)
        self.assertEqual(
            derived, str(uuid.uuid5(uuid.NAMESPACE_URL, f"agentforce:{sid}"))
        )

    def test_non_uuid_is_stable_uuid5(self) -> None:
        sid = "not-a-uuid"
        expected = str(uuid.uuid5(uuid.NAMESPACE_URL, f"agentforce:{sid}"))
        self.assertEqual(honeyhive_session_id(sid), expected)


class SpanKindTest(unittest.TestCase):
    def test_llm_step_is_chat(self) -> None:
        self.assertEqual(
            span_kind({"name": "chat"}, {"step.type": "LLM_STEP"}),
            "LLM",
        )
        self.assertEqual(operation_name("LLM"), "chat")

    def test_state_update_is_execute_tool(self) -> None:
        self.assertEqual(
            span_kind(
                {"name": "__state_update_action__"}, {"step.type": "VARIABLE_UPDATE_STEP"}
            ),
            "TOOL",
        )
        self.assertEqual(operation_name("TOOL"), "execute_tool")

    def test_turn_is_invoke_agent(self) -> None:
        self.assertEqual(span_kind({"name": "GeneralFAQ"}, {}), "CHAIN")
        self.assertEqual(operation_name("CHAIN"), "invoke_agent")


class AttrEncodingTest(unittest.TestCase):
    def test_dict_becomes_json_string(self) -> None:
        encoded = attr("input.value", {"messages": [{"role": "user", "content": "hi"}]})
        self.assertEqual(
            json.loads(encoded["value"]["stringValue"]),
            {"messages": [{"role": "user", "content": "hi"}]},
        )


class StampTest(unittest.TestCase):
    def test_stamps_public_session_and_operation_name(self) -> None:
        payload = _payload(
            "chat",
            [
                {"key": "step.type", "value": {"stringValue": "LLM_STEP"}},
                {"key": "gen_ai.request.model", "value": {"stringValue": "gpt-4o"}},
            ],
        )
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
        self.assertIn("honeyhive.session_auto_create", resource_keys)
        self.assertIn("honeyhive.session_name", resource_keys)
        self.assertIn("gen_ai.conversation.id", resource_keys)
        self.assertIn("gen_ai.agent.name", resource_keys)
        self.assertEqual(span_attrs["gen_ai.operation.name"]["stringValue"], "chat")
        self.assertNotIn("openinference.span.kind", span_attrs)
        self.assertEqual(
            span_attrs["gen_ai.request.model"]["stringValue"], "gpt-4o"
        )
        self.assertTrue(span_attrs["honeyhive.session_auto_create"]["boolValue"])
        self.assertEqual(
            span_attrs["honeyhive.session_name"]["stringValue"], "DemoAgent"
        )
        self.assertNotIn("honeyhive_event_type", span_attrs)
        self.assertFalse(
            any(key.startswith("honeyhive_inputs") for key in span_attrs)
        )


class IoRewriteTest(unittest.TestCase):
    def test_llm_kvlist_becomes_genai_json_strings(self) -> None:
        payload = _payload(
            "off_topic",
            [
                {"key": "step.type", "value": {"stringValue": "LLM_STEP"}},
                {
                    "key": "input.value",
                    "value": {
                        "kvlistValue": {
                            "gen_ai.request.model": "llmgateway__GPT41",
                            "gen_ai.input.messages": [
                                {"role": "system", "content": "You are an AI Agent."},
                                {
                                    "role": "user",
                                    "content": "What else can you do?",
                                },
                            ],
                        }
                    },
                },
                {
                    "key": "output.value",
                    "value": {
                        "kvlistValue": {
                            "gen_ai.output.messages": (
                                "I am here to help with AI-powered searches."
                            )
                        }
                    },
                },
            ],
        )
        stamp_and_map(payload, "5fd03ee0-c76d-4d57-9ed4-d43556ab8e73", "DemoAgent")
        strings = _span_attr_strings(payload)
        self.assertEqual(
            json.loads(strings["gen_ai.input.messages"]),
            [
                {"role": "system", "content": "You are an AI Agent."},
                {"role": "user", "content": "What else can you do?"},
            ],
        )
        self.assertEqual(
            json.loads(strings["gen_ai.output.messages"]),
            [
                {
                    "role": "assistant",
                    "content": "I am here to help with AI-powered searches.",
                }
            ],
        )
        self.assertNotIn("input.value", strings)
        self.assertNotIn("output.value", strings)
        self.assertEqual(strings["gen_ai.operation.name"], "chat")
        self.assertEqual(strings["gen_ai.request.model"], "llmgateway__GPT41")
        keys = set(strings)
        self.assertNotIn("honeyhive_event_type", keys)
        self.assertFalse(any(key.startswith("honeyhive_inputs") for key in keys))

    def test_turn_agent_messages_become_genai_json_strings(self) -> None:
        payload = _payload(
            "GeneralFAQ",
            [
                {
                    "key": "agent.messages.user.0.content",
                    "value": {"stringValue": "What is your purpose?"},
                },
                {
                    "key": "agent.messages.assistant.1.content",
                    "value": {
                        "stringValue": "I&#39;m here to search knowledge articles."
                    },
                },
            ],
        )
        stamp_and_map(payload, "5fd03ee0-c76d-4d57-9ed4-d43556ab8e73", "DemoAgent")
        strings = _span_attr_strings(payload)
        self.assertEqual(
            json.loads(strings["gen_ai.input.messages"]),
            [
                {"role": "user", "content": "What is your purpose?"},
                {
                    "role": "assistant",
                    "content": "I'm here to search knowledge articles.",
                },
            ],
        )
        self.assertEqual(
            json.loads(strings["gen_ai.output.messages"])[0]["content"],
            "I'm here to search knowledge articles.",
        )
        self.assertEqual(strings["gen_ai.operation.name"], "invoke_agent")
        self.assertNotIn("input.value", strings)
        self.assertNotIn("output.value", strings)
        self.assertNotIn("openinference.span.kind", strings)

    def test_classifier_uses_classifier_input_and_selected_target(self) -> None:
        payload = _payload(
            "pre_orchestration.guardrail",
            [
                {"key": "step.type", "value": {"stringValue": "CLASSIFIER_STEP"}},
                {
                    "key": "input.value",
                    "value": {
                        "kvlistValue": {
                            "classifier.input": "What else can you do?",
                        }
                    },
                },
                {
                    "key": "output.value",
                    "value": {
                        "kvlistValue": {
                            "af.router_classifier.selected_target": "Miscellaneous_Category"
                        }
                    },
                },
            ],
        )
        stamp_and_map(payload, "5fd03ee0-c76d-4d57-9ed4-d43556ab8e73", "DemoAgent")
        strings = _span_attr_strings(payload)
        self.assertEqual(
            json.loads(strings["gen_ai.input.messages"]),
            [{"role": "user", "content": "What else can you do?"}],
        )
        self.assertEqual(
            json.loads(strings["gen_ai.output.messages"])[0]["content"],
            "Miscellaneous_Category",
        )
        self.assertEqual(strings["gen_ai.operation.name"], "chat")
        self.assertNotIn("input.value", strings)
        self.assertNotIn("output.value", strings)
        self.assertNotIn("openinference.span.kind", strings)

    def test_state_update_stays_empty(self) -> None:
        payload = _payload(
            "__state_update_action__",
            [
                {
                    "key": "step.type",
                    "value": {"stringValue": "VARIABLE_UPDATE_STEP"},
                },
                {"key": "step.id", "value": {"stringValue": "abc"}},
            ],
        )
        stamp_and_map(payload, "5fd03ee0-c76d-4d57-9ed4-d43556ab8e73", "DemoAgent")
        strings = _span_attr_strings(payload)
        self.assertNotIn("gen_ai.input.messages", strings)
        self.assertNotIn("gen_ai.output.messages", strings)
        self.assertEqual(strings["gen_ai.operation.name"], "execute_tool")
        self.assertNotIn("openinference.span.kind", strings)

    def test_guardrail_without_messages_drops_leftover_input(self) -> None:
        payload = _payload(
            "InstructionAdherence",
            [
                {
                    "key": "step.type",
                    "value": {"stringValue": "TRUST_GUARDRAILS_STEP"},
                },
                {
                    "key": "input.value",
                    "value": {"kvlistValue": {"af.request_id": "abc"}},
                },
                {
                    "key": "output.value",
                    "value": {
                        "kvlistValue": {
                            "gen_ai.output.messages": "InstructionAdherence: value=HIGH"
                        }
                    },
                },
            ],
        )
        stamp_and_map(payload, "5fd03ee0-c76d-4d57-9ed4-d43556ab8e73", "DemoAgent")
        strings = _span_attr_strings(payload)
        self.assertNotIn("gen_ai.input.messages", strings)
        self.assertNotIn("input.value", strings)
        self.assertNotIn("output.value", strings)
        self.assertEqual(strings["gen_ai.operation.name"], "chat")
        self.assertEqual(
            json.loads(strings["gen_ai.output.messages"])[0]["content"],
            "InstructionAdherence: value=HIGH",
        )


if __name__ == "__main__":
    unittest.main()
