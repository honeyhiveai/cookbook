"""Durable exported / rejected session ledger."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

OPERATING_PIN = (
    "https://github.com/honeyhiveai/cookbook/blob/main/"
    "salesforce-agentforce-cookbook/OPERATING.md"
)

REJECT_MESSAGES = {
    "expired": (
        "Recorded {session_id} as rejected; its start timestamp is "
        "past Salesforce's 72-hour OTel window, so it cannot be "
        "re-exported (started {started})"
    ),
    "missing_start": (
        "Recorded {session_id} as rejected; the row has no readable "
        "start timestamp (missing_start). Pin SALESFORCE_SESSION_ID "
        "to retry, or fix the Data 360 row. Recovery: "
        f"{OPERATING_PIN}"
    ),
    "empty_missing_start": (
        "Recorded {session_id} as rejected; Salesforce returned no "
        "spans and no readable start (empty_missing_start). Pin "
        "SALESFORCE_SESSION_ID to retry, or fix the Data 360 row. "
        f"Recovery: {OPERATING_PIN}"
    ),
    "unreadable": (
        "Recorded {session_id} as rejected; the poller could not "
        "handle this payload. Retrying now re-runs the same failure. "
        "After you change the script, stop the poller and remove "
        "the ID from {exported_file} only while it is still inside "
        "72 hours (started {started}) and discovery still returns "
        "it, or pin SALESFORCE_SESSION_ID. Past 72 hours, do not "
        "remove the ID: the next pass records it as expired"
    ),
    "mapping": (
        "Recorded {session_id} as rejected; the poller could not "
        "handle this payload. Retrying now re-runs the same failure. "
        "After you change the script, stop the poller and remove "
        "the ID from {exported_file} only while it is still inside "
        "72 hours (started {started}) and discovery still returns "
        "it, or pin SALESFORCE_SESSION_ID. Past 72 hours, do not "
        "remove the ID: the next pass records it as expired"
    ),
    "hh_400": (
        "Recorded {session_id} as rejected; HoneyHive returned 400. "
        "That is a decode or size failure, so "
        "retrying now re-runs the same failure. After you fix the "
        "cause, stop the poller and remove the ID from "
        "{exported_file} only while it is still inside 72 hours "
        "(started {started}) and discovery still returns it, or pin "
        "SALESFORCE_SESSION_ID. Past 72 hours, do not remove the ID: "
        "the next pass records it as expired"
    ),
}


def _state_file_error(path: str, detail: str) -> SystemExit:
    return SystemExit(
        f"Could not read {path}: {detail} Repair it as "
        '{"exported": [...], "rejected": [...]}, or fix read permissions. '
        "Deleting it or pointing EXPORTED_FILE elsewhere starts from an "
        "empty record and re-exports every session in the discovery window"
    )


def load_reject_reasons(raw: object, path: str) -> dict[str, str]:
    reasons: dict[str, str] = {}
    if not isinstance(raw, dict):
        return reasons
    for key, value in raw.items():
        if not isinstance(key, str) or not key:
            continue
        if not isinstance(value, str):
            raise SystemExit(
                f"Could not read {path}: reject_reasons[{key!r}] must be a "
                "JSON string. Repair it, or omit reject_reasons entirely"
            )
        reasons[key] = value
    return reasons


def recover_leftover_tmp(path: str) -> None:
    tmp_path = f"{path}.tmp"
    if not os.path.isfile(tmp_path):
        return
    leftover_complete = False
    try:
        with open(tmp_path, encoding="utf-8") as leftover:
            json.load(leftover)
        leftover_complete = True
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        leftover_complete = False
    if leftover_complete:
        raise SystemExit(
            f"{tmp_path} already exists and parses as JSON. "
            "Stop anything writing this file (systemctl stop "
            "agentforce-poller if it is running under the unit), then "
            'confirm it is a JSON object with "exported" and "rejected" '
            "lists (what this write produces). Anything else, including "
            f"null, a number, or a bare list, parses but is not a leftover "
            f"record: delete {tmp_path} instead of moving it. Otherwise "
            f"move {tmp_path} onto {path}. Under the unit, systemctl "
            "reset-failed "
            "agentforce-poller before starting it again. Until you do, "
            "every start exits here rather than overwriting it. Pointing "
            "EXPORTED_FILE elsewhere instead starts from an empty record "
            "and re-exports every session in the discovery window"
        )
    try:
        os.unlink(tmp_path)
    except OSError as error:
        raise SystemExit(
            f"{tmp_path} already exists, does not parse, and could not "
            f"be removed: {error}. Delete {tmp_path} by hand. Do not "
            f"move it onto {path}; {path} itself is unchanged. "
            "Pointing EXPORTED_FILE elsewhere instead starts from an "
            "empty record and re-exports every session in the "
            "discovery window"
        )


def load_exported(path: str) -> tuple[set[str], set[str], dict[str, str]]:
    recover_leftover_tmp(path)
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        return set(), set(), {}
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as error:
        raise _state_file_error(path, f"{error}.")
    if isinstance(data, list):
        return {str(item) for item in data}, set(), {}
    if isinstance(data, dict):
        exported = data.get("exported")
        rejected = data.get("rejected")
        reasons_raw = data.get("reject_reasons")
        if reasons_raw is not None and not isinstance(reasons_raw, dict):
            raise SystemExit(
                f"Could not read {path}: reject_reasons must be a JSON object. "
                'Repair it as {"exported": [...], "rejected": [...]}. Deleting it '
                "or pointing EXPORTED_FILE elsewhere starts from an empty record "
                "and re-exports every session in the discovery window"
            )
        if isinstance(exported, list) and isinstance(rejected, list):
            return (
                {str(item) for item in exported},
                {str(item) for item in rejected},
                load_reject_reasons(reasons_raw, path),
            )
        bad = [
            key
            for key in ("exported", "rejected")
            if not isinstance(data.get(key), list)
        ]
        raise SystemExit(
            f"Could not read {path}: {' and '.join(bad)} must be a JSON list. "
            'Repair it as {"exported": [...], "rejected": [...]}. Deleting it '
            "or pointing EXPORTED_FILE elsewhere starts from an empty record "
            "and re-exports every session in the discovery window"
        )
    raise SystemExit(
        f"Could not read {path}: expected a JSON object, got "
        f"{type(data).__name__}. Repair it as "
        '{"exported": [...], "rejected": [...]}. Deleting it or pointing '
        "EXPORTED_FILE elsewhere starts from an empty record and re-exports "
        "every session in the discovery window"
    )


def save_exported(
    path: str, exported: set[str], rejected: set[str], reasons: dict[str, str]
) -> None:
    tmp_path = f"{path}.tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "exported": sorted(exported),
                    "rejected": sorted(rejected),
                    "reject_reasons": {
                        sid: reasons[sid]
                        for sid in sorted(rejected)
                        if sid in reasons
                    },
                },
                handle,
            )
    except OSError as error:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise SystemExit(
            f"Could not write {path}: {error}. {tmp_path} is incomplete; "
            f"do not move it onto {path}. If {tmp_path} is still there, "
            f"delete it. Creating {tmp_path} needs write and execute on "
            f"the directory that holds {path}, not only on {path}. Fix "
            f"those permissions or free space, or point EXPORTED_FILE at "
            f"a writable path. If the parent of {path} does not exist "
            f"yet, pin with the default relative EXPORTED_FILE first: pass "
            f"EXPORTED_FILE= on the pin command, or leave the key out of "
            f"poller.env until after the pin, then set the absolute path "
            f"in poller.env before Start the poller. "
            "That chain creates the parent. Do not create it as agentforce "
            "before you pin. "
            "Pointing elsewhere starts from an empty record and re-exports "
            "every session in the discovery window"
        )
    try:
        os.replace(tmp_path, path)
    except OSError as error:
        raise SystemExit(
            f"Could not write {path}: {error}. {tmp_path} is complete. "
            "Stop anything writing this file (systemctl stop "
            "agentforce-poller if it is running under the unit), then move "
            f"{tmp_path} onto {path}. Under the unit, systemctl reset-failed "
            "agentforce-poller before starting it again. "
            "Until you do, every start exits on that leftover rather "
            "than overwriting it. Pointing EXPORTED_FILE elsewhere "
            "instead starts from an empty record and re-exports every "
            "session in the discovery window"
        )


@dataclass
class Ledger:
    path: str
    persist: bool
    exported: set[str] = field(default_factory=set)
    rejected: set[str] = field(default_factory=set)
    reasons: dict[str, str] = field(default_factory=dict)
    starts: dict[str, str] = field(default_factory=dict)

    @classmethod
    def load(cls, path: str, persist: bool) -> Ledger:
        if not persist:
            return cls(path=path, persist=False)
        exported, rejected, reasons = load_exported(path)
        ledger = cls(
            path=path,
            persist=True,
            exported=exported,
            rejected=rejected,
            reasons=reasons,
        )
        ledger.save()
        return ledger

    def save(self) -> None:
        if self.persist:
            save_exported(self.path, self.exported, self.rejected, self.reasons)

    def record_export(self, session_id: str) -> None:
        self.exported.add(session_id)
        self.rejected.discard(session_id)
        self.reasons.pop(session_id, None)
        self.save()

    def record_reject(self, session_id: str, reason: str) -> None:
        self.reasons[session_id] = reason
        self.rejected.add(session_id)
        if not self.persist:
            return
        self.save()
        template = REJECT_MESSAGES.get(reason)
        if template:
            print(
                template.format(
                    session_id=session_id,
                    started=self.starts.get(session_id, "unknown"),
                    exported_file=self.path,
                )
            )
