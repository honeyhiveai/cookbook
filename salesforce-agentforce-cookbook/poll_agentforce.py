#!/usr/bin/env python3
"""Discover Agentforce sessions, fetch Session Trace OTel, POST to HoneyHive."""

from __future__ import annotations

import json
import os
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from otel_map import honeyhive_session_id, iter_spans, session_name_for, stamp_and_map

API_VERSION = os.environ.get("SALESFORCE_API_VERSION", "v66.0").strip() or "v66.0"
WINDOW_DAYS = int(os.environ.get("DISCOVERY_WINDOW_DAYS", "4") or "4")
DISCOVERY_LIMIT = int(os.environ.get("DISCOVERY_LIMIT", "20") or "20")
IDLE_SECONDS = int(os.environ.get("SESSION_IDLE_SECONDS", "120") or "120")
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "60") or "60")
MAX_PASSES = int(os.environ.get("MAX_PASSES", "1") or "1")
EXPORTED_FILE = (
    os.environ.get("EXPORTED_FILE", ".agentforce-exported.json").strip()
    or ".agentforce-exported.json"
)


class HttpError(Exception):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code


def env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"Set {name}")
    return value


def dry_run() -> bool:
    return os.environ.get("DRY_RUN", "").strip().lower() in ("1", "true", "yes")


def resolved_session_id(sf_session_id: str) -> str:
    override = os.environ.get("HONEYHIVE_SESSION_ID", "").strip()
    if not override:
        return honeyhive_session_id(sf_session_id)
    try:
        return str(uuid.UUID(override))
    except ValueError:
        raise SystemExit("HONEYHIVE_SESSION_ID must be a UUID") from None


def http_json(method: str, url: str, headers: dict, data=None, form: bool = False):
    body = None
    req_headers = dict(headers)
    if data is not None:
        if form:
            body = urllib.parse.urlencode(data).encode()
            req_headers["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            body = json.dumps(data).encode()
            req_headers.setdefault("Content-Type", "application/json")
    request = urllib.request.Request(url, data=body, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            raw = response.read()
            if not raw:
                return {}
            return json.loads(raw.decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        err = exc.read().decode("utf-8", "replace")[:1000]
        if err:
            print(err)
        raise HttpError(exc.code, f"{method} {url} failed: HTTP {exc.code}") from exc


def discovery_soql(window_days: int, limit: int) -> str:
    # LAST_N_DAYS:n is a range that already ends at now. Use =, not >.
    where = ""
    if window_days > 0:
        where = f"WHERE ssot__StartTimestamp__c = LAST_N_DAYS:{window_days} "
    return (
        "SELECT ssot__Id__c, ssot__StartTimestamp__c, ssot__EndTimestamp__c "
        "FROM ssot__AiAgentSession__dlm "
        f"{where}"
        "ORDER BY ssot__StartTimestamp__c DESC NULLS LAST "
        f"LIMIT {limit}"
    )


def salesforce_token(instance: str) -> str:
    payload = http_json(
        "POST",
        f"{instance}/services/oauth2/token",
        {},
        {
            "grant_type": "client_credentials",
            "client_id": env("SALESFORCE_CLIENT_ID"),
            "client_secret": env("SALESFORCE_CLIENT_SECRET"),
        },
        form=True,
    )
    token = payload.get("access_token")
    if not token:
        raise SystemExit("no access_token in the token response")
    return str(token)


def discover_sessions(instance: str, headers: dict) -> list[dict]:
    query = http_json(
        "GET",
        (
            f"{instance}/services/data/{API_VERSION}/query/"
            f"?q={urllib.parse.quote(discovery_soql(WINDOW_DAYS, DISCOVERY_LIMIT))}"
        ),
        headers,
    )
    records = query.get("records")
    if not isinstance(records, list):
        return []
    return [record for record in records if isinstance(record, dict) and record.get("ssot__Id__c")]


def fetch_otel(instance: str, headers: dict, session_id: str) -> dict:
    payload = http_json(
        "GET",
        (
            f"{instance}/services/data/{API_VERSION}/einstein/audit/otel/"
            f"{urllib.parse.quote(session_id, safe='')}"
        ),
        {**headers, "Accept": "application/json"},
    )
    if not isinstance(payload, dict):
        raise SystemExit(f"OTel response for {session_id} was not an object")
    return payload


def latest_span_end_unix(payload: dict) -> int:
    latest = 0
    for span in iter_spans(payload):
        try:
            end_ns = int(span.get("endTimeUnixNano") or 0)
        except (TypeError, ValueError):
            continue
        if end_ns > latest:
            latest = end_ns
    return latest


def session_is_complete(session: dict, payload: dict) -> bool:
    end_timestamp = session.get("ssot__EndTimestamp__c")
    if isinstance(end_timestamp, str) and end_timestamp.strip():
        return True
    latest_ns = latest_span_end_unix(payload)
    if latest_ns <= 0:
        return False
    age_seconds = time.time() - (latest_ns / 1_000_000_000)
    return age_seconds >= IDLE_SECONDS


def skip_reason(*, complete: bool, count: int) -> str | None:
    if count == 0:
        return "no spans yet, Data 360 join is still catching up"
    if not complete:
        return "in-progress"
    return None


def end_label(record: dict) -> str:
    if "ssot__EndTimestamp__c" not in record:
        return "unknown"
    raw = record.get("ssot__EndTimestamp__c")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return "unset"


def load_exported(path: str) -> set[str]:
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        return set()
    if isinstance(data, list):
        return {str(item) for item in data}
    if isinstance(data, dict) and isinstance(data.get("exported"), list):
        return {str(item) for item in data["exported"]}
    return set()


def save_exported(path: str, exported: set[str]) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(sorted(exported), handle)


def parse_sf_timestamp(value) -> float | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    if len(text) >= 5 and text[-5] in "+-" and text[-3] != ":":
        text = f"{text[:-2]}:{text[-2:]}"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def past_72h(record: dict) -> bool:
    start = parse_sf_timestamp(record.get("ssot__StartTimestamp__c"))
    if start is None:
        return False
    return (time.time() - start) >= 72 * 3600


def process_session(
    record: dict,
    *,
    instance: str,
    sf_headers: dict,
    hh_url: str,
    hh_key: str,
    pin: bool,
    preview: bool,
    exported: set[str],
) -> bool:
    session_id = str(record["ssot__Id__c"])
    try:
        payload = fetch_otel(instance, sf_headers, session_id)
    except HttpError as exc:
        print(f"Skip {session_id}: HTTP {exc.code}")
        return False
    count = len(list(iter_spans(payload)))
    complete = pin or session_is_complete(record, payload)
    reason = skip_reason(complete=complete, count=count)
    if reason:
        if not pin and count == 0 and past_72h(record):
            print(f"Skip {session_id}: no spans and start is past 72 hours")
            return False
        print(f"Skip {session_id}: {reason}")
        return False
    hh_session = resolved_session_id(session_id)
    stamp_and_map(payload, hh_session, session_name_for(payload, None))
    if preview:
        print(
            f"Would export {count} span(s) for {session_id} as {hh_session} "
            f"(ended {end_label(record)})"
        )
        return False
    try:
        http_json(
            "POST",
            f"{hh_url}/opentelemetry/v1/traces",
            {"Authorization": f"Bearer {hh_key}"},
            payload,
        )
    except HttpError as exc:
        print(f"HoneyHive POST failed for {session_id}: {exc}")
        return False
    print(f"Exported {count} span(s) for {session_id} as {hh_session}")
    exported.add(session_id)
    save_exported(EXPORTED_FILE, exported)
    return True


def run_pass(
    *,
    instance: str,
    hh_url: str,
    hh_key: str,
    only: str,
    preview: bool,
    exported: set[str],
) -> None:
    try:
        token = salesforce_token(instance)
    except HttpError as exc:
        raise SystemExit(str(exc)) from exc
    sf_headers = {"Authorization": f"Bearer {token}"}
    pin = bool(only)
    if pin:
        sessions = [{"ssot__Id__c": only}]
    else:
        try:
            sessions = discover_sessions(instance, sf_headers)
        except HttpError as exc:
            raise SystemExit(str(exc)) from exc
    pending = [
        record
        for record in sessions
        if pin or str(record["ssot__Id__c"]) not in exported
    ]
    print(f"Discovered {len(sessions)} session(s), {len(pending)} pending")
    if pending:
        print("Pending: " + ", ".join(str(record["ssot__Id__c"]) for record in pending))
    for record in pending:
        process_session(
            record,
            instance=instance,
            sf_headers=sf_headers,
            hh_url=hh_url,
            hh_key=hh_key,
            pin=pin,
            preview=preview,
            exported=exported,
        )


def main() -> None:
    instance = env("SALESFORCE_INSTANCE_URL").rstrip("/")
    if not instance.startswith("https://"):
        raise SystemExit("SALESFORCE_INSTANCE_URL must start with https://")
    preview = dry_run()
    hh_url = ""
    hh_key = ""
    if not preview:
        hh_url = env("HH_API_URL").rstrip("/")
        hh_key = env("HH_API_KEY")
        if not hh_url.startswith(("https://", "http://")):
            raise SystemExit("HH_API_URL must start with https:// or http://")
    only = os.environ.get("SALESFORCE_SESSION_ID", "").strip()
    exported = set() if preview else load_exported(EXPORTED_FILE)
    passes = 0
    while True:
        run_pass(
            instance=instance,
            hh_url=hh_url,
            hh_key=hh_key,
            only=only,
            preview=preview,
            exported=exported,
        )
        passes += 1
        if MAX_PASSES != 0 and passes >= MAX_PASSES:
            break
        print(f"Sleeping {POLL_INTERVAL}s")
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
