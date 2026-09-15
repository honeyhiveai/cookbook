"""Zero-config sanity check: minimal ACS manifest + Rego + the manual acs_guard.

Run this first to confirm your ACS + OPA + HoneyHive wiring before adapting the
full bank_agent example. It uses the annotator-free manifest under ``minimal/``
(guards ``pre_tool_call`` deny/escalate and ``output`` transform) and the
explicit :func:`make_acs_guard` wrapper so you can see one ACS evaluation map to
one HoneyHive span.

Usage:
    export ACS_OPA_PATH=/path/to/opa
    export HH_API_KEY=...
    python minimal_smoke.py
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from agent_control_specification import AgentControl, InterventionPoint
from honeyhive import HoneyHiveTracer

from acs_honeyhive import make_acs_guard

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "minimal" / "manifest.yaml"

SOURCE = "acs-minimal-smoke"
SESSION_NAME = "acs-minimal-smoke"


async def main() -> int:
    load_dotenv(override=True)
    if not os.getenv("HH_API_KEY"):
        print("ERROR: HH_API_KEY is not set.", file=sys.stderr)
        return 2
    if not os.getenv("ACS_OPA_PATH"):
        print("ERROR: ACS_OPA_PATH is not set (see scripts/setup_opa.sh).", file=sys.stderr)
        return 2

    HoneyHiveTracer.init(
        api_key=os.getenv("HH_API_KEY"),
        source=SOURCE,
        session_name=SESSION_NAME,
    )

    control = AgentControl.from_path(str(MANIFEST))
    acs_guard = make_acs_guard(control)

    cases = [
        (
            InterventionPoint.PRE_TOOL_CALL,
            {"tool_call": {"id": "t1", "name": "send_email", "args": {"to": "bob@external.com"}}},
        ),
        (
            InterventionPoint.PRE_TOOL_CALL,
            {"tool_call": {"id": "t2", "name": "wire_payment", "args": {"amount": 5000}}},
        ),
        (InterventionPoint.OUTPUT, {"output": "Your SSN is 123-45-6789, thanks."}),
        (InterventionPoint.OUTPUT, {"output": "All good, nothing sensitive here."}),
    ]

    print(f"manifest : {MANIFEST}")
    print(f"opa      : {os.getenv('ACS_OPA_PATH')}")
    print("-" * 60)
    for intervention_point, snapshot in cases:
        result = await acs_guard(intervention_point, snapshot)
        verdict = result.verdict
        print(
            f"{intervention_point.value:16s} -> {verdict.decision.value:9s} "
            f"| {verdict.reason or ''} | transformed={result.transformed_policy_target!r}"
        )

    HoneyHiveTracer.flush_all()
    print("-" * 60)
    print(f"Flushed spans to HoneyHive (source='{SOURCE}', session_name='{SESSION_NAME}').")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
