"""Behavior specs for discovery SOQL and skip decisions."""

from __future__ import annotations

import unittest

from poll_agentforce import discovery_soql, skip_reason


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


if __name__ == "__main__":
    unittest.main()
