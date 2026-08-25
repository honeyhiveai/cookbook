"""Behavior specs for discovery SOQL, skip decisions, and session id override."""

from __future__ import annotations

import os
import unittest
import uuid
from unittest.mock import patch

from otel_map import honeyhive_session_id
from poll_agentforce import discovery_soql, resolved_session_id, skip_reason


class DiscoverySoqlTest(unittest.TestCase):
    def test_window_uses_equals_last_n_days(self) -> None:
        query = discovery_soql(4, 20)
        self.assertIn("ssot__StartTimestamp__c = LAST_N_DAYS:4", query)
        self.assertNotIn(">", query)
        self.assertIn("LIMIT 20", query)

    def test_zero_window_has_no_time_filter(self) -> None:
        query = discovery_soql(0, 20)
        self.assertNotIn("LAST_N_DAYS", query)


class SkipReasonTest(unittest.TestCase):
    def test_empty_skips_even_when_complete(self) -> None:
        self.assertIn("no spans yet", skip_reason(complete=True, count=0) or "")

    def test_in_progress_with_spans_skips(self) -> None:
        self.assertEqual(skip_reason(complete=False, count=3), "in-progress")

    def test_complete_with_spans_exports(self) -> None:
        self.assertIsNone(skip_reason(complete=True, count=20))


class ResolvedSessionIdTest(unittest.TestCase):
    def test_default_is_uuid5(self) -> None:
        sid = "01a02190-7c5e-74ee-b4a8-eff86af959e7"
        with patch.dict(os.environ, {"HONEYHIVE_SESSION_ID": ""}):
            self.assertEqual(resolved_session_id(sid), honeyhive_session_id(sid))

    def test_override_must_be_uuid(self) -> None:
        override = str(uuid.uuid4())
        with patch.dict(os.environ, {"HONEYHIVE_SESSION_ID": override}):
            self.assertEqual(resolved_session_id("ignored"), override)


if __name__ == "__main__":
    unittest.main()
