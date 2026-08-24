"""Behavior specs for idle/window/empty-span decisions."""

from __future__ import annotations

import unittest

from policy import decide_after_fetch


class DecideAfterFetchTest(unittest.TestCase):
    def test_in_progress_with_spans_skips(self) -> None:
        decision = decide_after_fetch(
            complete=False,
            count=3,
            window_reason=None,
            pin=False,
            session_id="sid",
        )
        self.assertEqual(decision.kind, "skip")
        self.assertIn("in-progress", decision.message)

    def test_incomplete_empty_expired_rejects(self) -> None:
        decision = decide_after_fetch(
            complete=False,
            count=0,
            window_reason="expired",
            pin=False,
            session_id="sid",
        )
        self.assertEqual(decision.kind, "reject")
        self.assertEqual(decision.reason, "expired")

    def test_incomplete_empty_join_lag_skips(self) -> None:
        decision = decide_after_fetch(
            complete=False,
            count=0,
            window_reason=None,
            pin=False,
            session_id="sid",
        )
        self.assertEqual(decision.kind, "skip")
        self.assertIn("join is still catching up", decision.message)

    def test_complete_empty_missing_start_rejects_empty_slug(self) -> None:
        decision = decide_after_fetch(
            complete=True,
            count=0,
            window_reason="missing_start",
            pin=False,
            session_id="sid",
        )
        self.assertEqual(decision.kind, "reject")
        self.assertEqual(decision.reason, "empty_missing_start")
        self.assertIn("empty spans", decision.message)

    def test_pin_empty_does_not_reject(self) -> None:
        decision = decide_after_fetch(
            complete=True,
            count=0,
            window_reason="missing_start",
            pin=True,
            session_id="sid",
        )
        self.assertEqual(decision.kind, "skip")
        self.assertEqual(decision.reason, "")

    def test_complete_with_spans_exports(self) -> None:
        decision = decide_after_fetch(
            complete=True,
            count=20,
            window_reason=None,
            pin=False,
            session_id="sid",
        )
        self.assertIsNone(decision)


if __name__ == "__main__":
    unittest.main()
