"""Create/update the online evaluators from the YAML files in evaluators/.

The spec's `honeyhive metrics create` CLI path does not exist in honeyhive 1.5.1
— the shipped CLI has no `metrics` command and registers no console script — so
this posts to the REST API instead. `filters` IS accepted there (verified against
the generated CreateMetricRequest model).

    python evaluators/apply_evaluators.py            # create/update both
    python evaluators/apply_evaluators.py --dry-run  # print payloads only
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

EVAL_DIR = Path(__file__).resolve().parent
DEFAULT_BASE = "https://api.dp1.us.honeyhive.ai"


def _request(method: str, url: str, api_key: str, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode()
            return resp.status, (json.loads(body) if body else None)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    load_dotenv()
    api_key = os.getenv("HH_API_KEY", "").strip()
    base = os.getenv("HH_API_URL", DEFAULT_BASE).rstrip("/")

    if not api_key and not args.dry_run:
        print("HH_API_KEY is not set.", file=sys.stderr)
        return 2

    files = sorted(EVAL_DIR.glob("*.yaml"))
    if not files:
        print(f"No evaluator YAML found in {EVAL_DIR}", file=sys.stderr)
        return 1

    existing = {}
    if not args.dry_run:
        status, body = _request("GET", f"{base}/v1/metrics", api_key)
        if status == 200 and isinstance(body, list):
            existing = {m.get("name"): m.get("id") for m in body}
        elif status == 200 and isinstance(body, dict):
            for m in body.get("metrics", []) or []:
                existing[m.get("name")] = m.get("id")
        else:
            print(f"  ! could not list existing metrics (HTTP {status}); "
                  f"will attempt creates", file=sys.stderr)

    rc = 0
    for path in files:
        spec = yaml.safe_load(path.read_text())
        name = spec["name"]

        if spec.get("sampling_percentage") != 100:
            print(f"  ! {name}: sampling_percentage is "
                  f"{spec.get('sampling_percentage')}, expected 100")

        print(f"\n=== {name} ({path.name}) ===")
        if args.dry_run:
            print(json.dumps(spec, indent=2)[:1500])
            continue

        if name in existing:
            # the update endpoint expects `id`; `metric_id` is rejected as an
            # unrecognized key
            payload = dict(spec, id=existing[name])
            status, body = _request("PUT", f"{base}/v1/metrics", api_key, payload)
            action = "updated"
        else:
            status, body = _request("POST", f"{base}/v1/metrics", api_key, spec)
            action = "created"

        # HTTP 200 alone is not proof of persistence — check the body, then
        # confirm by re-listing. A create that silently does not stick would
        # otherwise be reported as success.
        persisted = isinstance(body, dict) and (
            body.get("inserted") or body.get("updated") or body.get("metric_id")
        )
        if status in (200, 201) and persisted:
            print(f"  {action} OK  (metric_id={body.get('metric_id')})")
        elif status in (200, 201):
            rc = 1
            print(f"  HTTP {status} but response does not confirm persistence: "
                  f"{str(body)[:300]}", file=sys.stderr)
        else:
            rc = 1
            print(f"  FAILED HTTP {status}: {str(body)[:1500]}", file=sys.stderr)

    if not args.dry_run:
        status, body = _request("GET", f"{base}/v1/metrics", api_key)
        live = body if isinstance(body, list) else (body or {}).get("metrics", [])
        by_name = {m.get("name"): m for m in live}
        print("\n=== confirmed live in project ===")
        for path in files:
            name = yaml.safe_load(path.read_text())["name"]
            m = by_name.get(name)
            if not m:
                rc = 1
                print(f"  MISSING: {name} is not in the project", file=sys.stderr)
            else:
                sp = m.get("sampling_percentage")
                flag = "" if sp == 100 else "   <-- NOT 100"
                print(f"  {name}: type={m.get('type')} return_type={m.get('return_type')} "
                      f"enabled={m.get('enabled_in_prod')} sampling={sp}{flag}")
                if sp != 100:
                    rc = 1
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
