"""Idle, 72-hour window, empty-payload, and fetch-error decisions."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from otel_map import iter_spans

DecisionKind = Literal["export", "skip", "reject", "fatal"]


@dataclass(frozen=True)
class Decision:
    kind: DecisionKind
    message: str = ""
    reason: str = ""
    exit_message: str = ""


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


def session_is_complete(session: dict, payload: dict, idle_seconds: int) -> bool:
    end_timestamp = session.get("ssot__EndTimestamp__c")
    if isinstance(end_timestamp, str) and end_timestamp.strip():
        return True
    latest_ns = latest_span_end_unix(payload)
    if latest_ns <= 0:
        return False
    age_seconds = time.time() - (latest_ns / 1_000_000_000)
    return age_seconds >= idle_seconds


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


def start_label(record: dict) -> str:
    raw = record.get("ssot__StartTimestamp__c")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return "unknown"


def end_label(record: dict) -> str:
    if "ssot__EndTimestamp__c" not in record:
        return "unknown"
    raw = record.get("ssot__EndTimestamp__c")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return "unset"


def otel_window_expired(
    session: dict, warned_ids: set[str] | None = None
) -> str | None:
    raw = session.get("ssot__StartTimestamp__c")
    start = parse_sf_timestamp(raw)
    if start is None:
        if not isinstance(raw, str) or not raw.strip():
            return "missing_start"
        session_id = str(session.get("ssot__Id__c") or "")
        if warned_ids is None or session_id not in warned_ids:
            print(
                f"Could not read ssot__StartTimestamp__c={raw!r}; "
                f"will retry {session.get('ssot__Id__c')}"
            )
            if warned_ids is not None and session_id:
                warned_ids.add(session_id)
        return None
    if (time.time() - start) >= 72 * 3600:
        return "expired"
    return None


def decide_after_fetch(
    *,
    complete: bool,
    count: int,
    window_reason: str | None,
    pin: bool,
    session_id: str,
) -> Decision | None:
    if not complete:
        if count:
            return Decision(kind="skip", message=f"Skip in-progress {session_id}")
        if window_reason == "expired":
            return Decision(
                kind="reject",
                message=(
                    f"Skip {session_id}: no spans and the start "
                    "timestamp is past Salesforce's 72-hour OTel "
                    "window"
                ),
                reason="expired",
            )
        return Decision(
            kind="skip",
            message=(
                f"Skip {session_id}: no spans yet, Data 360 "
                "join is still catching up"
            ),
        )
    if count == 0:
        if window_reason and not pin:
            return Decision(
                kind="reject",
                message=f"Skip {session_id}: empty spans",
                reason=(
                    "empty_missing_start"
                    if window_reason == "missing_start"
                    else window_reason
                ),
            )
        return Decision(
            kind="skip",
            message=(
                f"Skip {session_id}: no spans yet, Data 360 "
                "join is still catching up"
            ),
        )
    return None


def decide_fetch_error(
    *,
    pin: bool,
    fatal: bool,
    code: int | None,
    window_reason: str | None,
    instance: str,
    api_version: str,
    session_id: str,
) -> Decision:
    if not fatal:
        return Decision(kind="skip")
    if code in (400, 404):
        if pin:
            return Decision(
                kind="fatal",
                exit_message=(
                    f"Giving up on {session_id}: Salesforce rejected the fetch. "
                    "Unknown session ID, or the session is past the 72-hour window, "
                    f"or the org does not support {api_version}. "
                    f"GET {instance}/services/data/ lists the versions "
                    "the org does support"
                ),
            )
        if window_reason:
            return Decision(kind="reject", reason=window_reason)
        return Decision(kind="skip")
    return Decision(
        kind="fatal",
        exit_message=(
            "Giving up: Salesforce denied the OTel fetch. "
            "Check that the ECA Run As user can read Einstein "
            "Audit data (Setup > Einstein Audit, Analytics, and "
            "Monitoring Setup), or whether API access is enabled "
            "for the org"
        ),
    )


def expired_band_message(window_days: int) -> str | None:
    if window_days in (1, 2):
        return None
    future = (
        "Lowering DISCOVERY_WINDOW_DAYS only affects future passes; "
        "IDs already recorded stay rejected"
    )
    if window_days == 0:
        return (
            "Expired sessions stay in discovery after Salesforce's "
            "72-hour OTel window. At DISCOVERY_WINDOW_DAYS=0 there is "
            "no time filter, so this band is unbounded. Set 3 to bound "
            f"it at 24 hours, unless the org rejected that literal. {future}"
        )
    if window_days > 3:
        return (
            "Expired sessions stay in discovery after Salesforce's "
            "72-hour OTel window. 3 shrinks the band to at most 24 "
            "hours and still covers the full window; lower than 3 "
            f"drops sessions Salesforce would still export. {future}"
        )
    if window_days == 3:
        return (
            "Expired sessions stay in discovery after Salesforce's "
            "72-hour OTel window. DISCOVERY_WINDOW_DAYS is already 3, "
            "so the band is at most 24 hours and still covers the "
            f"full window. {future}"
        )
    return None
