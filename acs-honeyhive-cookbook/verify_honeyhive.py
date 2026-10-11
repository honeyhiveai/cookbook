"""Verify that ACS decision spans landed in HoneyHive.

Queries the HoneyHive events API for spans emitted by ``bank_agent_runner.py``
and asserts that the full decision matrix (allow / deny / escalate / transform /
warn) is present under the demo source.

Note: ``enrich_span`` stores dotted metadata keys nested, so ``acs.decision`` is
read back as ``metadata["acs"]["decision"]``.

Usage:
    export HH_API_KEY=...
    export HH_PROJECT="Your Project"   # optional; backend infers from key
    python verify_honeyhive.py
"""
from __future__ import annotations

import os
import sys
import time

from dotenv import load_dotenv

from honeyhive import HoneyHive

SOURCE = "acs-bank-demo"
EXPECTED_DECISIONS = {"allow", "deny", "escalate", "transform", "warn"}


def _acs_metadata(event: object) -> dict:
    meta = getattr(event, "metadata", None)
    if not isinstance(meta, dict):
        meta = {}
    acs = meta.get("acs")
    return acs if isinstance(acs, dict) else {}


def main() -> int:
    load_dotenv(override=True)
    api_key = os.getenv("HH_API_KEY")
    if not api_key:
        print("ERROR: HH_API_KEY is not set.", file=sys.stderr)
        return 2

    hh = HoneyHive(api_key=api_key, server_url=os.getenv("HH_API_URL"))
    project = os.getenv("HH_PROJECT")

    # Spans are ingested asynchronously; poll briefly for them to appear.
    decisions: set[str] = set()
    rows: list[tuple[str, str]] = []
    for attempt in range(6):
        resp = hh.events.get_events(
            project=project,
            filters=[{"field": "source", "operator": "is", "value": SOURCE}],
            limit=200,
        )
        events = getattr(resp, "events", None) or []
        decisions.clear()
        rows.clear()
        for event in events:
            acs = _acs_metadata(event)
            if not acs:
                continue
            decision = acs.get("decision")
            if decision:
                decisions.add(decision)
                rows.append((acs.get("intervention_point", "?"), decision))
        if EXPECTED_DECISIONS.issubset(decisions):
            break
        print(f"  ... waiting for ingestion (attempt {attempt + 1}/6, found {sorted(decisions)})")
        time.sleep(10)

    print("-" * 60)
    print(f"ACS spans found under source='{SOURCE}':")
    for intervention_point, decision in sorted(set(rows)):
        print(f"  {intervention_point:16s} {decision}")
    print("-" * 60)
    print(f"Decision types observed: {sorted(decisions)}")

    missing = EXPECTED_DECISIONS - decisions
    if missing:
        print(f"MISSING decision types: {sorted(missing)}", file=sys.stderr)
        return 1
    print("OK: all decision types (allow/deny/escalate/transform/warn) present in HoneyHive.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
