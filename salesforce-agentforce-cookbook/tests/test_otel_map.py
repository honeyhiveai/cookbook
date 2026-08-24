"""Behavior specs for session ID and first-write-wins mapping."""

from __future__ import annotations

import unittest
import uuid

from otel_map import honeyhive_session_id, map_io


class SessionIdTest(unittest.TestCase):
    def test_uuid_passthrough(self) -> None:
        sid = "5fd03ee0-c76d-4d57-9ed4-d43556ab8e73"
        self.assertEqual(honeyhive_session_id(sid), sid)

    def test_non_uuid_is_stable_uuid5(self) -> None:
        sid = "not-a-uuid"
        expected = str(uuid.uuid5(uuid.NAMESPACE_URL, f"agentforce:{sid}"))
        self.assertEqual(honeyhive_session_id(sid), expected)
        self.assertEqual(honeyhive_session_id(sid), honeyhive_session_id(sid))


class MapIoFirstWriteWinsTest(unittest.TestCase):
    def test_gen_ai_wins_over_agent_messages(self) -> None:
        attrs = {
            "input.value": {
                "gen_ai.input.messages": [
                    {"role": "user", "content": "from gen_ai"},
                ]
            },
            "output.value": {
                "gen_ai.output.messages": [
                    {"role": "assistant", "content": "gen_ai completion"},
                ]
            },
            "agent.messages.user.0.content": "from agent messages",
            "agent.messages.assistant.0.content": "agent assistant",
        }
        inputs, outputs, _config = map_io(attrs)
        self.assertEqual(inputs["chat_history"][0]["content"], "from gen_ai")
        self.assertEqual(outputs["content"], "gen_ai completion")

    def test_agent_messages_fill_when_gen_ai_missing(self) -> None:
        attrs = {
            "agent.messages.user.0.content": "user turn",
            "agent.messages.assistant.0.content": "assistant turn",
        }
        inputs, outputs, _config = map_io(attrs)
        self.assertEqual(inputs["user_message"], "user turn")
        self.assertEqual(outputs["content"], "assistant turn")


if __name__ == "__main__":
    unittest.main()
