#!/usr/bin/env python3
"""Discover Agentforce sessions, fetch Session Trace OTel, POST to HoneyHive."""

from __future__ import annotations

import json
import time

from config import Settings, load_settings
from net import (
    FETCH_ERRORS,
    HttpFailure,
    error_text,
    honeyhive_post_result,
    http_json,
    is_fatal_http,
)
from otel_map import honeyhive_session_id, iter_spans, session_name_for, stamp_and_map
from policy import (
    decide_after_fetch,
    decide_fetch_error,
    end_label,
    expired_band_message,
    otel_window_expired,
    session_is_complete,
    start_label,
)
from salesforce_api import discover_sessions, fetch_otel, salesforce_token
from state import Ledger


def try_export(
    payload: dict,
    count: int,
    session_id: str,
    hh_session: str,
    dry_run: bool,
    hh_url: str,
    hh_key: str,
    ended: str,
) -> str:
    if dry_run:
        print(
            f"Would export {count} span(s) for {session_id} as {hh_session} "
            f"(ended {ended})"
        )
        return "ok"
    try:
        http_json(
            "POST",
            f"{hh_url}/opentelemetry/v1/traces",
            {"Authorization": f"Bearer {hh_key}"},
            payload,
        )
    except json.JSONDecodeError:
        print(f"HoneyHive accepted {session_id} but returned a non-JSON body")
    except FETCH_ERRORS as exc:
        print(f"HoneyHive POST failed for {session_id}: {error_text(exc)}")
        return honeyhive_post_result(exc)
    print(f"Exported {count} span(s) for {session_id} as {hh_session}")
    return "ok"


def sleep_unless_done(passes: int, max_passes: int, interval: int) -> bool:
    """Return True when the loop should stop. Otherwise sleep for interval."""
    if max_passes and passes >= max_passes:
        return True
    print(f"Sleeping {interval}s")
    time.sleep(interval)
    return False


def warn_expired_band(settings: Settings, warned: list[bool]) -> None:
    if warned[0]:
        return
    message = expired_band_message(settings.window_days)
    if message is None:
        return
    warned[0] = True
    print(message)


def handle_decision(
    decision,
    *,
    settings: Settings,
    ledger: Ledger,
    session_id: str,
    expired_warned: list[bool],
) -> None:
    if decision.message:
        print(decision.message)
    if decision.kind == "fatal":
        raise SystemExit(decision.exit_message)
    if decision.kind == "reject" and settings.persist:
        ledger.record_reject(session_id, decision.reason)
        if decision.reason == "expired":
            warn_expired_band(settings, expired_warned)


def process_session(
    record: dict,
    *,
    settings: Settings,
    ledger: Ledger,
    sf_headers: dict,
    pin: bool,
    expired_warned: list[bool],
    unparseable_start_warned: set[str],
) -> bool:
    """Return True when this session was exported."""
    session_id = str(record["ssot__Id__c"])
    try:
        payload = fetch_otel(
            settings.instance, sf_headers, session_id, settings.api_version
        )
    except FETCH_ERRORS as exc:
        print(f"Skip {session_id}: {error_text(exc)}")
        window_reason = None
        if is_fatal_http(exc) and isinstance(exc, HttpFailure) and exc.code in (400, 404):
            window_reason = otel_window_expired(record, unparseable_start_warned)
        decision = decide_fetch_error(
            pin=pin,
            fatal=is_fatal_http(exc),
            code=exc.code if isinstance(exc, HttpFailure) else None,
            window_reason=window_reason,
            instance=settings.instance,
            api_version=settings.api_version,
            session_id=session_id,
        )
        handle_decision(
            decision,
            settings=settings,
            ledger=ledger,
            session_id=session_id,
            expired_warned=expired_warned,
        )
        return False
    try:
        count = len(list(iter_spans(payload)))
        complete = pin or session_is_complete(record, payload, settings.idle_seconds)
    except (AttributeError, TypeError, ValueError) as exc:
        print(f"Skip {session_id}: could not read payload: {exc}")
        if pin:
            raise SystemExit(f"Giving up on {session_id}: payload could not be read")
        ledger.record_reject(session_id, "unreadable")
        return False
    window_reason = (
        otel_window_expired(record, unparseable_start_warned) if count == 0 else None
    )
    decision = decide_after_fetch(
        complete=complete,
        count=count,
        window_reason=window_reason,
        pin=pin,
        session_id=session_id,
    )
    if decision is not None:
        handle_decision(
            decision,
            settings=settings,
            ledger=ledger,
            session_id=session_id,
            expired_warned=expired_warned,
        )
        return False
    hh_session = honeyhive_session_id(session_id)
    if pin and settings.hh_override:
        hh_session = settings.hh_override
    try:
        stamp_and_map(
            payload,
            hh_session,
            session_name_for(
                payload, settings.session_name_override if pin else None
            ),
        )
    except (AttributeError, ValueError, TypeError, RecursionError) as exc:
        print(f"Skip {session_id}: could not map payload: {exc}")
        if pin:
            raise SystemExit(f"Giving up on {session_id}: mapping failed")
        ledger.record_reject(session_id, "mapping")
        return False
    result = try_export(
        payload,
        count,
        session_id,
        hh_session,
        settings.dry_run,
        settings.hh_url,
        settings.hh_key,
        end_label(record),
    )
    if result == "auth":
        raise SystemExit(
            f"HoneyHive rejected the export for {session_id}. "
            "401 or 403: check HH_API_KEY. 404: check HH_API_URL - "
            "the traces path is wrong, not the payload."
        )
    if result != "ok":
        if pin and result == "reject":
            raise SystemExit(
                f"Giving up on {session_id}: HoneyHive POST failed"
            )
        if result == "reject":
            ledger.record_reject(session_id, "hh_400")
        return False
    ledger.record_export(session_id)
    return True


def rejected_label(sid: str, ledger: Ledger) -> str:
    started = ledger.starts.get(sid, "unknown")
    if sid in ledger.reasons:
        return f"{sid} ({ledger.reasons[sid]}, started {started})"
    return f"{sid} (started {started})"


def print_pass(
    discovered: int,
    pending: list,
    rejected_here: list[str],
    ledger: Ledger,
    settings: Settings,
    limit_warned: list[bool],
) -> None:
    print(
        f"Discovered {discovered} session(s), "
        f"{len(pending)} pending, {len(rejected_here)} rejected"
    )
    if pending:
        print(
            "Pending: "
            + ", ".join(str(record["ssot__Id__c"]) for record in pending)
        )
    if rejected_here:
        print("Rejected: " + ", ".join(rejected_label(sid, ledger) for sid in rejected_here))
    if (
        not settings.only
        and discovered >= settings.discovery_limit
        and not limit_warned[0]
    ):
        limit_warned[0] = True
        print(
            f"Hit DISCOVERY_LIMIT={settings.discovery_limit}; older sessions in the "
            "window are not returned, and new conversations push the oldest "
            "out of this result. Raise DISCOVERY_LIMIT to reach the rest, "
            "while they are inside DISCOVERY_WINDOW_DAYS and Salesforce's "
            "72-hour export window"
        )


def auth_or_discover(
    settings: Settings, pin: bool
) -> tuple[list, int, dict]:
    token = salesforce_token(settings.instance)
    sf_headers = {"Authorization": f"Bearer {token}"}
    if pin:
        return [{"ssot__Id__c": settings.only}], 1, sf_headers
    sessions, discovered = discover_sessions(
        settings.instance,
        sf_headers,
        settings.window_days,
        settings.discovery_limit,
        settings.api_version,
    )
    return sessions, discovered, sf_headers


def handle_auth_failure(
    exc: BaseException, settings: Settings, pin: bool
) -> None:
    print(f"Auth or discovery failed: {error_text(exc)}")
    if not is_fatal_http(exc):
        return
    if pin:
        raise SystemExit(
            "Giving up: Salesforce rejected the token request. "
            "Check SALESFORCE_CLIENT_ID, SALESFORCE_CLIENT_SECRET, "
            "and the api scope, or whether API access is enabled "
            "for the org. A 404 here usually means "
            f"SALESFORCE_INSTANCE_URL is not the org's My Domain "
            f"login host: GET {settings.instance}/services/data/ should "
            "list API versions"
        )
    if isinstance(exc, HttpFailure) and exc.code == 403:
        raise SystemExit(
            "Giving up: Salesforce denied auth or discovery. "
            "Check Data Cloud access for the ECA Run As user, "
            "or whether API access is enabled for the org"
        )
    raise SystemExit(
        "Giving up: Salesforce rejected auth or discovery. "
        "Check SALESFORCE_CLIENT_SECRET and the api scope, or "
        "SALESFORCE_INSTANCE_URL if it is not the org's My Domain "
        "login host, or set "
        "DISCOVERY_WINDOW_DAYS=0 if the org rejected the query, "
        "or SALESFORCE_API_VERSION if the org does not support "
        f"{settings.api_version}. GET {settings.instance}/services/data/ lists the "
        "versions the org does support"
    )


def run_loop(settings: Settings, ledger: Ledger, pin: bool) -> None:
    passes = 0
    limit_warned = [False]
    expired_warned = [False]
    unparseable_start_warned: set[str] = set()
    exported_pin = False
    while True:
        try:
            sessions, discovered, sf_headers = auth_or_discover(settings, pin)
        except FETCH_ERRORS as exc:
            handle_auth_failure(exc, settings, pin)
            passes += 1
            if sleep_unless_done(passes, settings.max_passes, settings.interval):
                if pin and not exported_pin:
                    raise SystemExit(
                        f"Gave up on {settings.only} after {passes} pass(es) "
                        "without exporting"
                    )
                raise SystemExit(
                    f"Stopped after {passes} pass(es); the last pass "
                    "could not authenticate or discover sessions"
                )
            continue

        ledger.starts = {
            str(record["ssot__Id__c"]): start_label(record)
            for record in sessions
            if record.get("ssot__Id__c")
        }
        pending = [
            record
            for record in sessions
            if (
                str(record["ssot__Id__c"]) not in ledger.exported
                and str(record["ssot__Id__c"]) not in ledger.rejected
            )
            or pin
        ]
        rejected_here = [
            str(record["ssot__Id__c"])
            for record in sessions
            if str(record["ssot__Id__c"]) in ledger.rejected
        ]
        print_pass(
            discovered, pending, rejected_here, ledger, settings, limit_warned
        )
        for record in pending:
            if process_session(
                record,
                settings=settings,
                ledger=ledger,
                sf_headers=sf_headers,
                pin=pin,
                expired_warned=expired_warned,
                unparseable_start_warned=unparseable_start_warned,
            ):
                exported_pin = True
                if pin:
                    return
        passes += 1
        if sleep_unless_done(passes, settings.max_passes, settings.interval):
            if pin and not exported_pin:
                raise SystemExit(
                    f"Gave up on {settings.only} after {passes} pass(es) "
                    "without exporting"
                )
            break


def main() -> None:
    settings = load_settings()
    ledger = Ledger.load(settings.exported_file, settings.persist)
    run_loop(settings, ledger, pin=bool(settings.only))


if __name__ == "__main__":
    main()
