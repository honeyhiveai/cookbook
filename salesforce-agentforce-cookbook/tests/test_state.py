"""Behavior specs for leftover state-file recovery."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from state import load_exported, recover_leftover_tmp, save_exported


class LeftoverTmpTest(unittest.TestCase):
    def test_parseable_leftover_exits_before_load(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "state.json")
            leftover = f"{path}.tmp"
            with open(leftover, "w", encoding="utf-8") as handle:
                json.dump({"exported": ["a"], "rejected": []}, handle)
            with self.assertRaises(SystemExit) as raised:
                load_exported(path)
            self.assertIn("already exists and parses as JSON", str(raised.exception))
            self.assertTrue(Path(leftover).is_file())

    def test_unreadable_leftover_is_removed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "state.json")
            leftover = f"{path}.tmp"
            with open(leftover, "w", encoding="utf-8") as handle:
                handle.write("{not-json")
            exported, rejected, reasons = load_exported(path)
            self.assertEqual(exported, set())
            self.assertEqual(rejected, set())
            self.assertEqual(reasons, {})
            self.assertFalse(Path(leftover).is_file())

    def test_save_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "state.json")
            save_exported(path, {"b", "a"}, {"c"}, {"c": "expired"})
            exported, rejected, reasons = load_exported(path)
            self.assertEqual(exported, {"a", "b"})
            self.assertEqual(rejected, {"c"})
            self.assertEqual(reasons, {"c": "expired"})
            self.assertFalse(Path(f"{path}.tmp").exists())


if __name__ == "__main__":
    unittest.main()
