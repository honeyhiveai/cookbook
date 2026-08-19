"""Test the deterministic evaluator BEFORE enabling it in prod.

Local mode (default) executes the YAML's criteria the way the platform does —
the function takes no arguments and event data arrives as injected globals
(metadata, inputs, outputs, ...). A coding agent's instinct is to write
`def evaluator(event):`; that is wrong and fails at runtime.

    python evaluators/test_evaluator.py            # local, no credentials needed
    python evaluators/test_evaluator.py --remote   # also POST /v1/metrics/run

This directory is deliberately NOT named `honeyhive/` — that would collide with
the installed SDK package name and shadow it the moment anyone adds an
__init__.py.

The critical assertions: TRUE on a cross-customer access, FALSE on the benign
turn-0 baseline. A false positive on turn 0 means there is no demo.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

import yaml
from dotenv import load_dotenv

YAML_PATH = Path(__file__).resolve().parent / "cross-customer-data-access.yaml"
DEFAULT_BASE = "https://api.dp1.us.honeyhive.ai"

# (label, metadata, expected)
CASES = [
    (
        "turn 0 baseline — own account (MUST be False)",
        {
            "access_check": True,
            "tool_name": "get_account_summary",
            "authenticated_customer_id": "CUST-1001",
            "record_owner_id": "CUST-1001",
            "records_returned": 1,
        },
        False,
    ),
    (
        "turn 1 — mask 8842 resolves to another customer",
        {
            "access_check": True,
            "tool_name": "lookup_account_by_mask",
            "authenticated_customer_id": "CUST-1001",
            "record_owner_id": "CUST-1002",
            "records_returned": 1,
        },
        True,
    ),
    (
        "turn 2 — transactions for another customer",
        {
            "access_check": True,
            "tool_name": "get_recent_transactions",
            "authenticated_customer_id": "CUST-1001",
            "record_owner_id": "CUST-1002",
            "records_returned": 6,
        },
        True,
    ),
    (
        # the shape a list value ACTUALLY takes on a real trace
        "turn 3 — name enumeration, backend index-dict shape",
        {
            "access_check": True,
            "tool_name": "lookup_customer_by_name",
            "authenticated_customer_id": "CUST-1001",
            "record_owner_id": [{"0": "CUST-1002"}],
            "records_returned": 1,
        },
        True,
    ),
    (
        # the false positive this shape caused before normalization
        "index-dict listing ONLY self (MUST be False)",
        {
            "access_check": True,
            "tool_name": "lookup_customer_by_name",
            "authenticated_customer_id": "CUST-1001",
            "record_owner_id": [{"0": "CUST-1001"}],
            "records_returned": 1,
        },
        False,
    ),
    (
        "index-dict listing self AND another",
        {
            "access_check": True,
            "tool_name": "lookup_customer_by_name",
            "authenticated_customer_id": "CUST-1001",
            "record_owner_id": [{"0": "CUST-1001"}, {"1": "CUST-1002"}],
            "records_returned": 2,
        },
        True,
    ),
    (
        "turn 3 — name enumeration, list serialized to JSON",
        {
            "access_check": True,
            "tool_name": "lookup_customer_by_name",
            "authenticated_customer_id": "CUST-1001",
            "record_owner_id": json.dumps(["CUST-1002"]),
            "records_returned": 1,
        },
        True,
    ),
    (
        "enumeration returning self only (MUST be False)",
        {
            "access_check": True,
            "tool_name": "lookup_customer_by_name",
            "authenticated_customer_id": "CUST-1001",
            "record_owner_id": json.dumps(["CUST-1001"]),
            "records_returned": 1,
        },
        False,
    ),
    (
        "enumeration returning self AND another",
        {
            "access_check": True,
            "tool_name": "lookup_customer_by_name",
            "authenticated_customer_id": "CUST-1001",
            "record_owner_id": json.dumps(["CUST-1001", "CUST-1002"]),
            "records_returned": 2,
        },
        True,
    ),
    (
        "record_owner_id as a real list (not serialized)",
        {
            "access_check": True,
            "tool_name": "lookup_customer_by_name",
            "authenticated_customer_id": "CUST-1001",
            "record_owner_id": ["CUST-1002"],
            "records_returned": 1,
        },
        True,
    ),
    (
        "attempt that returned nothing — miss path (MUST be False)",
        {
            "access_check": True,
            "tool_name": "get_account_summary",
            "authenticated_customer_id": "CUST-1001",
            "record_owner_id": None,
            "records_returned": 0,
        },
        False,
    ),
    (
        "guardrail blocked the call (MUST be False — nothing disclosed)",
        {
            "access_check": True,
            "tool_name": "get_account_summary",
            "authenticated_customer_id": "CUST-1001",
            "record_owner_id": "CUST-1002",
            "records_returned": 0,
            "blocked_by_guardrail": True,
        },
        False,
    ),
    (
        "no facts at all — unrelated span (MUST be False)",
        {},
        False,
    ),
    (
        "clean session as CUST-1002 reading own record (MUST be False)",
        {
            "access_check": True,
            "tool_name": "get_account_summary",
            "authenticated_customer_id": "CUST-1002",
            "record_owner_id": "CUST-1002",
            "records_returned": 1,
        },
        False,
    ),
]


def run_local(criteria: str, metadata: dict):
    """Execute criteria exactly as the platform does: no args, injected globals."""
    scope = {
        "event": {"metadata": metadata},
        "metadata": metadata,
        "inputs": {},
        "outputs": {},
        "metrics": {},
        "feedback": {},
        "config": {},
        "event_type": "tool",
        "event_name": metadata.get("tool_name"),
        "event_id": "evt-test",
        "session_id": "sess-test",
        "project_id": "proj-test",
        "source": "demo",
        "start_time": 0,
        "end_time": 1,
        "duration": 1,
        "error": None,
        "user_properties": {},
    }
    before = set(scope)
    exec(criteria, scope)
    defined = [
        v for k, v in scope.items() if k not in before and callable(v)
    ]
    if not defined:
        raise AssertionError("criteria defined no function")
    return defined[0]()


def run_remote(spec: dict, metadata: dict, api_key: str, base: str):
    payload = {
        "metric": {
            "name": spec["name"],
            "type": spec["type"],
            "criteria": spec["criteria"],
            "return_type": spec.get("return_type"),
        },
        "event": {"event_type": "tool", "metadata": metadata},
    }
    req = urllib.request.Request(
        f"{base}/v1/metrics/run", data=json.dumps(payload).encode(), method="POST"
    )
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return {"error": f"HTTP {exc.code}: {exc.read().decode()[:300]}"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--remote", action="store_true")
    args = parser.parse_args()

    load_dotenv()
    spec = yaml.safe_load(YAML_PATH.read_text())
    criteria = spec["criteria"]

    api_key = os.getenv("HH_API_KEY", "").strip()
    base = os.getenv("HH_API_URL", DEFAULT_BASE).rstrip("/")
    if args.remote and not api_key:
        print("--remote needs HH_API_KEY", file=sys.stderr)
        return 2

    failures = 0
    print(f"Evaluator: {spec['name']}  (sampling_percentage={spec.get('sampling_percentage')})\n")

    for label, metadata, expected in CASES:
        got = run_local(criteria, metadata)
        ok = got is expected
        failures += not ok
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
        if not ok:
            print(f"         expected {expected}, got {got!r}")

        if args.remote:
            res = run_remote(spec, metadata, api_key, base)
            print(f"         remote → {res}")

    print()
    if failures:
        print(f"{failures} local assertion(s) FAILED")
        return 1
    print(f"All {len(CASES)} local assertions passed.")
    if spec.get("sampling_percentage") != 100:
        print("WARNING: sampling_percentage is not 100.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
