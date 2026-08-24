#!/usr/bin/env python3
"""Discover Agentforce sessions, fetch Session Trace OTel, POST to HoneyHive."""

import html
import http.client
import json
import os
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

FETCH_ERRORS = (
    # OSError covers URLError, HTTPError, TimeoutError, and a bare
    # ConnectionResetError from getresponse() or read(). HTTPException
    # covers IncompleteRead and RemoteDisconnected, which are not
    # URLError and would otherwise end the poll loop.
    OSError,
    http.client.HTTPException,
    KeyError,
    json.JSONDecodeError,
)


def error_text(exc: BaseException) -> str:
    # KeyError.__str__ is repr(args[0]), which adds quotes the docs do not show.
    if isinstance(exc, KeyError) and exc.args:
        return str(exc.args[0])
    return str(exc)


def discovery_soql(window_days: int, limit: int) -> str:
    # LAST_N_DAYS keeps the first pass from backfilling old org history
    # and from retrying sessions whose 72-hour OTel window has expired.
    where = ""
    if window_days > 0:
        where = f"WHERE ssot__StartTimestamp__c > LAST_N_DAYS:{window_days} "
    return (
        "SELECT ssot__Id__c, ssot__StartTimestamp__c, ssot__EndTimestamp__c "
        "FROM ssot__AiAgentSession__dlm "
        f"{where}"
        "ORDER BY ssot__StartTimestamp__c DESC NULLS LAST "
        f"LIMIT {limit}"
    )


def require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"Set {name}")
    return value


def env_int(name: str, default: str, minimum: int | None = None) -> int:
    raw = os.environ.get(name, default).strip() or default
    try:
        value = int(raw)
    except ValueError:
        raise SystemExit(f"{name} must be a whole number, got {raw!r}")
    return value if minimum is None else max(minimum, value)


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
                # An empty 200 body is not the Salesforce empty-session shell
                # (resourceSpans with an empty spans array). Raise so FETCH_ERRORS
                # retries it instead of aging the ID into an expired reject.
                raise json.JSONDecodeError("empty response body", "", 0)
            # json.loads on bytes raises UnicodeDecodeError, not JSONDecodeError,
            # for a body that is not valid UTF-8. Decode first so the failure
            # lands in FETCH_ERRORS instead of ending the poll loop.
            return json.loads(raw.decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        try:
            # Match the success path: replace undecodable bytes rather than
            # discarding the body, so is_fatal_http can still find its marker.
            body = exc.read().decode("utf-8", "replace")[:4000]
        except (OSError, http.client.HTTPException):
            body = ""
        if body:
            print(body[:1000])
        # http_json consumes the stream. is_fatal_http reads hh_body instead.
        setattr(exc, "hh_body", body)
        raise


def unescape(value):
    if isinstance(value, str):
        return html.unescape(value)
    if isinstance(value, list):
        return [unescape(item) for item in value]
    if isinstance(value, dict):
        return {key: unescape(item) for key, item in value.items()}
    return value


def any_value(value):
    if not isinstance(value, dict):
        return unescape(value)
    if "stringValue" in value:
        return unescape(value["stringValue"])
    if "intValue" in value:
        return int(value["intValue"])
    if "doubleValue" in value:
        return float(value["doubleValue"])
    if "boolValue" in value:
        return bool(value["boolValue"])
    if "bytesValue" in value:
        return value["bytesValue"]
    if "kvlistValue" in value:
        kv_list = value["kvlistValue"]
        if isinstance(kv_list, dict) and isinstance(kv_list.get("values"), list):
            return {
                item.get("key"): any_value(item.get("value") or {})
                for item in kv_list["values"]
                if item.get("key")
            }
        return unescape(kv_list)
    if "arrayValue" in value:
        items = (value["arrayValue"] or {}).get("values") or []
        return [any_value(item) if isinstance(item, dict) else unescape(item) for item in items]
    return unescape(value)


def attr(key: str, value) -> dict:
    if isinstance(value, bool):
        return {"key": key, "value": {"boolValue": value}}
    if isinstance(value, int):
        return {"key": key, "value": {"intValue": str(value)}}
    if isinstance(value, float):
        return {"key": key, "value": {"doubleValue": value}}
    if isinstance(value, (dict, list)):
        return {"key": key, "value": {"stringValue": json.dumps(value, default=str)}}
    return {"key": key, "value": {"stringValue": "" if value is None else str(value)}}


def set_prefixed(attrs: list, prefix: str, value) -> None:
    if value is None:
        return
    if isinstance(value, dict):
        for key, item in value.items():
            set_prefixed(attrs, f"{prefix}.{key}", item)
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            set_prefixed(attrs, f"{prefix}.{index}", item)
        return
    attrs.append(attr(prefix, value))


def span_attr_map(items: list) -> dict:
    mapped = {}
    for item in items or []:
        key = item.get("key")
        if key:
            mapped[key] = any_value(item.get("value") or {})
    return mapped


def iter_spans(payload: dict):
    for resource in payload.get("resourceSpans") or []:
        for scope in resource.get("scopeSpans") or []:
            yield from (scope.get("spans") or [])


def collect_spans(payload: dict) -> list:
    return list(iter_spans(payload))


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


def load_exported(path: str) -> tuple[set[str], set[str], dict[str, str]]:
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        return set(), set(), {}
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as error:
        # The file exists but is unreadable. Starting empty would re-export
        # every session in the window and then overwrite the record.
        raise SystemExit(
            f"Could not read {path}: {error}. Repair it as "
            '{"exported": [...], "rejected": [...]}, or fix read permissions. '
            "Deleting it or pointing EXPORTED_FILE elsewhere starts from an "
            "empty record and re-exports every session in the discovery window"
        )
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
    # A leftover tmp is from a previous persist that never replaced the
    # live file. Opening it with "w" would overwrite that record.
    if os.path.isfile(tmp_path):
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
        # Reached only when the leftover is unreadable and {path} is intact,
        # so there is nothing to adjudicate. Clear it and carry on rather
        # than wedging every later start on a file with no record in it.
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
        # A partial write leaves an invalid tmp file. Remove it so a later
        # "move the .tmp" recovery cannot overwrite a valid state file.
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


def mark_exported(
    exported: set[str],
    rejected: set[str],
    reasons: dict[str, str],
    session_id: str,
    exported_file: str,
    persist: bool,
) -> None:
    exported.add(session_id)
    rejected.discard(session_id)
    reasons.pop(session_id, None)
    if persist:
        save_exported(exported_file, exported, rejected, reasons)


def mark_rejected(
    exported: set[str],
    rejected: set[str],
    reasons: dict[str, str],
    session_id: str,
    exported_file: str,
    persist: bool,
    reason: str,
    started: str = "unknown",
) -> None:
    rejected.add(session_id)
    if persist:
        save_exported(exported_file, exported, rejected, reasons)
        if reason == "expired":
            print(
                f"Recorded {session_id} as rejected; its start timestamp is "
                "past Salesforce's 72-hour OTel window, so it cannot be "
                f"re-exported (started {started})"
            )
        elif reason == "missing_start":
            print(
                f"Recorded {session_id} as rejected; the row has no readable "
                "start timestamp (missing_start). Pin SALESFORCE_SESSION_ID "
                "to retry, or fix the Data 360 row. Recovery: "
                "https://docs.honeyhive.ai/v2/integrations/"
                "salesforce-agentforce-operations#pinning-a-session"
            )
        elif reason == "empty_missing_start":
            print(
                f"Recorded {session_id} as rejected; Salesforce returned no "
                "spans and no readable start (empty_missing_start). Pin "
                "SALESFORCE_SESSION_ID to retry, or fix the Data 360 row. "
                "Recovery: https://docs.honeyhive.ai/v2/integrations/"
                "salesforce-agentforce-operations#pinning-a-session"
            )
        elif reason in ("unreadable", "mapping"):
            print(
                f"Recorded {session_id} as rejected; the poller could not "
                "handle this payload. Retrying now re-runs the same failure. "
                f"After you change the script, stop the poller and remove "
                f"the ID from {exported_file} only while it is still inside "
                f"72 hours (started {started}) and discovery still returns "
                "it, or pin SALESFORCE_SESSION_ID. Past 72 hours, do not "
                "remove the ID: the next pass records it as expired"
            )
        elif reason == "hh_400":
            print(
                f"Recorded {session_id} as rejected; HoneyHive returned 400. "
                "That is a decode or size failure, so "
                "retrying now re-runs the same failure. After you fix the "
                f"cause, stop the poller and remove the ID from "
                f"{exported_file} only while it is still inside 72 hours "
                f"(started {started}) and discovery still returns it, or pin "
                "SALESFORCE_SESSION_ID. Past 72 hours, do not remove the ID: "
                "the next pass records it as expired"
            )


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
    # Data 360 often leaves EndTimestamp empty after the conversation ends.
    # Whitespace or a non-string is not evidence the conversation ended.
    end_timestamp = session.get("ssot__EndTimestamp__c")
    if isinstance(end_timestamp, str) and end_timestamp.strip():
        # Set EndTimestamp skips idle. Raising SESSION_IDLE_SECONDS has no
        # effect on this branch.
        return True
    # latest_span_end_unix is Salesforce event time on spans Data 360 has
    # joined, so join lag counts toward age_seconds. This also compares the
    # poller host's clock against Salesforce's, so keep the host NTP-synced:
    # a host clock ahead by more than SESSION_IDLE_SECONDS treats every
    # conversation as finished on its first pass. Set SESSION_IDLE_SECONDS
    # above human reply latency plus that lag.
    latest_ns = latest_span_end_unix(payload)
    if latest_ns <= 0:
        return False
    age_seconds = time.time() - (latest_ns / 1_000_000_000)
    return age_seconds >= idle_seconds


def parse_sf_timestamp(value) -> float | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    # Python 3.10 fromisoformat rejects an offset without a colon (+0000).
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
    # Rejected: and Recorded lines print this so the 72-hour recovery
    # rule is checkable without querying Data 360 again.
    raw = record.get("ssot__StartTimestamp__c")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return "unknown"


def end_label(record: dict) -> str:
    # Would export prints this so the idle vs EndTimestamp branch
    # is pickable without querying Data 360 again. A pin builds its
    # own row with no timestamp columns, so report that as unknown
    # rather than claiming Salesforce left the field empty.
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
            # No start we can ever read (possible with DISCOVERY_WINDOW_DAYS=0,
            # where the SOQL filter no longer excludes null timestamps).
            # Do not retry forever. This is not a 72-hour comparison.
            return "missing_start"
        # A value we could not read is not evidence the window has passed.
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


def honeyhive_session_id(sf_session_id: str) -> str:
    try:
        return str(uuid.UUID(sf_session_id))
    except ValueError:
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"agentforce:{sf_session_id}"))


def maybe_json(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def leftover_bucket(value):
    # Use maybe_json only to detect a JSON object or array on a stringValue.
    # A scalar round-trip changes what Salesforce sent ("null" would drop
    # the payload, "false" -> "False", "1.50" -> "1.5"). Keep the original.
    parsed = maybe_json(value)
    if isinstance(parsed, (dict, list)):
        # An empty container carries nothing; do not store "{}" or "[]".
        return json.dumps(parsed, default=str) if parsed else None
    if value in (None, ""):
        return None
    return str(value)


def message_text(value) -> str:
    value = maybe_json(value)
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = [message_text(item) for item in value]
        return "\n".join(part for part in parts if part)
    if isinstance(value, dict):
        for key in ("content", "text", "message"):
            if value.get(key):
                return message_text(value[key])
        if value.get("role") and value.get("parts"):
            return message_text(value["parts"])
    return ""


def as_messages(value) -> list:
    value = maybe_json(value)
    if isinstance(value, list):
        messages = []
        for item in value:
            if isinstance(item, dict):
                role = item.get("role") or "user"
                content = message_text(item)
                if content:
                    messages.append({"role": role, "content": content})
            elif isinstance(item, str) and item:
                messages.append({"role": "user", "content": item})
        return messages
    if isinstance(value, str) and value:
        return [{"role": "user", "content": value}]
    return []


def last_content(messages: list, roles: tuple[str, ...]) -> str:
    for message in reversed(messages):
        if message.get("role") in roles and message.get("content"):
            return message["content"]
    return ""


def agent_message_index(key: str) -> tuple[int, str] | None:
    if not key.endswith(".content"):
        return None
    for role in ("user", "assistant"):
        prefix = f"agent.messages.{role}."
        if not key.startswith(prefix):
            continue
        try:
            return int(key[len(prefix) : -len(".content")]), role
        except ValueError:
            return None
    return None


def map_io(attrs: dict) -> tuple:
    inputs: dict = {}
    outputs: dict = {}
    config: dict = {}
    in_val = maybe_json(attrs.get("input.value"))
    out_val = maybe_json(attrs.get("output.value"))
    chat_history = []

    if isinstance(in_val, dict):
        if in_val.get("gen_ai.request.model"):
            config["model"] = in_val["gen_ai.request.model"]
        chat_history = as_messages(in_val.get("gen_ai.input.messages"))
        if not chat_history and in_val.get("classifier.input"):
            chat_history = [{"role": "user", "content": message_text(in_val["classifier.input"])}]
    elif isinstance(in_val, str) and in_val:
        chat_history = [{"role": "user", "content": in_val}]

    if isinstance(out_val, dict):
        out_messages = as_messages(out_val.get("gen_ai.output.messages"))
        content = last_content(out_messages, ("assistant", "model", "Output"))
        if not content:
            content = message_text(out_val.get("gen_ai.output.messages"))
        if not content:
            content = (
                message_text(out_val.get("af.router_classifier.selected_target"))
                or message_text(out_val.get("mgr.sensitive.step.result"))
            )
        if content:
            outputs["role"] = "assistant"
            outputs["content"] = content
        if out_val.get("gen_ai.request.model") and "model" not in config:
            config["model"] = out_val["gen_ai.request.model"]

    indexed = []
    for key, value in attrs.items():
        parsed = agent_message_index(key) if isinstance(key, str) else None
        if parsed is None:
            continue
        index, role = parsed
        text = value if isinstance(value, str) else message_text(value)
        if not text:
            continue
        indexed.append((index, role, text))
    if indexed:
        indexed.sort(key=lambda item: (item[0], 0 if item[1] == "user" else 1))
        # agent.messages.* and gen_ai.input.messages can carry the same turns.
        # Extending an already-populated chat_history stores each turn twice,
        # and openinference_values rebuilds input.value from it.
        if not chat_history:
            chat_history.extend(
                {"role": role, "content": text} for _, role, text in indexed
            )
        # Do not replace a gen_ai.output.messages completion already in
        # outputs["content"].
        if not outputs.get("content"):
            for _, role, text in reversed(indexed):
                if role == "assistant":
                    outputs["role"] = "assistant"
                    outputs["content"] = text
                    break

    if chat_history:
        inputs["chat_history"] = chat_history
        user_text = last_content(chat_history, ("user", "human"))
        if user_text:
            inputs["user_message"] = user_text
    return inputs, outputs, config


def openinference_values(attrs: dict, inputs: dict, outputs: dict, config: dict) -> tuple:
    in_val = maybe_json(attrs.get("input.value"))
    out_val = maybe_json(attrs.get("output.value"))
    input_payload = None
    output_payload = None
    if inputs.get("chat_history"):
        input_payload = {"messages": inputs["chat_history"]}
        if config.get("model"):
            input_payload["model"] = config["model"]
    elif isinstance(in_val, (dict, list, str)) and in_val:
        if isinstance(in_val, (dict, list)):
            input_payload = in_val
        else:
            input_payload = {"messages": [{"role": "user", "content": in_val}]}
    if outputs.get("content"):
        output_payload = {
            "role": outputs.get("role") or "assistant",
            "content": outputs["content"],
        }
    elif isinstance(out_val, (dict, list, str)) and out_val:
        if isinstance(out_val, (dict, list)):
            output_payload = out_val
        else:
            output_payload = {"role": "assistant", "content": out_val}
    return input_payload, output_payload


def event_type_for(span: dict, attrs: dict) -> str:
    name = span.get("name") or ""
    step_type = str(attrs.get("step.type") or "")
    in_val = maybe_json(attrs.get("input.value"))
    model_steps = {
        "LLM_STEP",
        "CLASSIFIER_STEP",
        "TOPIC_STEP",
        "TRUST_GUARDRAILS_STEP",
    }
    if step_type in model_steps or name in (
        "agent_router",
        "pre_orchestration.guardrail",
        "InstructionAdherence",
    ):
        return "model"
    if isinstance(in_val, dict) and (
        "gen_ai.input.messages" in in_val or "classifier.input" in in_val
    ):
        return "model"
    if name == "__state_update_action__" or step_type == "VARIABLE_UPDATE_STEP":
        return "tool"
    return "chain"


def flatten_any_value(value):
    if not isinstance(value, dict):
        return {"stringValue": "" if value is None else unescape(str(value))}
    if "kvlistValue" in value or "arrayValue" in value:
        return {"stringValue": json.dumps(any_value(value), default=str)}
    if "stringValue" in value:
        return {"stringValue": unescape(value["stringValue"])}
    return value


def flatten_attributes(items: list) -> None:
    for item in items or []:
        if "value" in item:
            item["value"] = flatten_any_value(item["value"])


def replace_or_add(items: list, key: str, value) -> None:
    encoded = attr(key, value)
    for item in items:
        if item.get("key") == key:
            item["value"] = encoded["value"]
            return
    items.append(encoded)


def drop_keys(items: list, keys: set[str]) -> None:
    items[:] = [item for item in items if item.get("key") not in keys]


def stamp_session(attrs: list, hh_session_id: str, session_name: str) -> None:
    attrs.append(attr("honeyhive.session_id", hh_session_id))
    attrs.append(attr("honeyhive.session_auto_create", True))
    attrs.append(attr("honeyhive.session_name", session_name))


def map_span(span: dict) -> None:
    # setdefault returns JSON null when the key is present. An empty list is
    # falsy, so `get(...) or []` would allocate a new list and drop stamps
    # already appended to the existing one.
    items = span.get("attributes")
    if not isinstance(items, list):
        items = []
        span["attributes"] = items
    raw = span_attr_map(items)
    inputs, outputs, config = map_io(raw)
    event_type = event_type_for(span, raw)
    flatten_attributes(items)
    # Any non-empty input.value/output.value is a model indicator in hive-kube
    # (CorrectEventType priority 3) and overrides honeyhive_event_type. Keep
    # those keys only on model spans, as OpenInference JSON strings.
    if event_type == "model":
        input_payload, output_payload = openinference_values(raw, inputs, outputs, config)
        if input_payload is not None:
            replace_or_add(items, "input.value", json.dumps(input_payload, default=str))
        if output_payload is not None:
            replace_or_add(items, "output.value", json.dumps(output_payload, default=str))
    else:
        # honeyhive_inputs/outputs are not priority-3 model indicators, so the
        # leftover payload can be kept there after the raw keys are dropped.
        # leftover_bucket JSON-encodes dict/list: set_prefixed joins with ".",
        # and ingest splits honeyhive_inputs.* on "." (SetNestedValue), so a
        # dotted Salesforce key would explode into nested objects and a
        # leaf/prefix pair would silently drop one side.
        leftover_in = leftover_bucket(raw.get("input.value"))
        if not inputs and leftover_in is not None:
            inputs["value"] = leftover_in
        leftover_out = leftover_bucket(raw.get("output.value"))
        if not outputs and leftover_out is not None:
            outputs["value"] = leftover_out
        drop_keys(items, {"input.value", "output.value"})
    additions = [attr("honeyhive_event_type", event_type)]
    set_prefixed(additions, "honeyhive_inputs", inputs)
    set_prefixed(additions, "honeyhive_outputs", outputs)
    set_prefixed(additions, "honeyhive_config", config)
    items.extend(additions)


def stamp_and_map(payload: dict, hh_session_id: str, session_name: str) -> None:
    for resource in payload.get("resourceSpans") or []:
        res = resource.get("resource")
        if not isinstance(res, dict):
            res = {}
            resource["resource"] = res
        resource_attrs = res.get("attributes")
        if not isinstance(resource_attrs, list):
            resource_attrs = []
            res["attributes"] = resource_attrs
        flatten_attributes(resource_attrs)
        # hive-kube CorrectEventType runs before honeyhive_event_type, and
        # mergeAttributes copies resource attributes onto every span, so a
        # resource key here classifies the whole payload.
        #
        # Dropped below: gen_ai.agent.name / agent_name (priority 2.6 returns
        # chain without gen_ai.request.model) and input.value / output.value
        # (priority 3 returns model). map_span reads input.value and
        # output.value off the span, never the resource.
        #
        # Not dropped, because this org's live dump carries none of them on
        # the resource. Add them here if yours does: openinference.span.kind
        # (priority 1, any mappable value), gen_ai.operation.name (priority
        # 2.5), and the rest of priority 3 - llm.request.type,
        # llm.input_messages, gen_ai.request.model, gen_ai.prompt,
        # gen_ai.completion, gen_ai.prompt.*, gen_ai.completion.*,
        # _event.gen_ai.user.message, _event.gen_ai.choice,
        # _event.gen_ai.input.message, and _event.gen_ai.output.message.
        #
        # CorrectEventType runs per span against the merged map, and span
        # attributes win over resource ones, so add the same keys to the
        # span drop_keys below. input.value / output.value are already
        # handled per span by map_span, which keeps them only on model spans.
        drop_keys(
            resource_attrs,
            {"gen_ai.agent.name", "agent_name", "input.value", "output.value"},
        )
        stamp_session(resource_attrs, hh_session_id, session_name)
        for scope in resource.get("scopeSpans") or []:
            for span in scope.get("spans") or []:
                span_attrs = span.get("attributes")
                if not isinstance(span_attrs, list):
                    span_attrs = []
                    span["attributes"] = span_attrs
                # Stamp after map_span, so flatten_attributes does not unescape
                # the session name a second time. The resource path above does
                # the same, and span attributes win in hive-kube mergeAttributes.
                map_span(span)
                stamp_session(span_attrs, hh_session_id, session_name)
                drop_keys(span_attrs, {"gen_ai.agent.name", "agent_name"})


def session_name_for(payload: dict, allow_override: bool) -> str:
    if allow_override:
        override = os.environ.get("HONEYHIVE_SESSION_NAME", "").strip()
        if override:
            return override
    for resource in payload.get("resourceSpans") or []:
        mapped = span_attr_map((resource.get("resource") or {}).get("attributes"))
        agent = mapped.get("session.actors.0.name") or mapped.get("gen_ai.agent.name")
        if agent:
            return str(agent)
    return "Agentforce"


def salesforce_token(instance: str) -> str:
    payload = http_json(
        "POST",
        f"{instance}/services/oauth2/token",
        {},
        {
            "grant_type": "client_credentials",
            "client_id": require("SALESFORCE_CLIENT_ID"),
            "client_secret": require("SALESFORCE_CLIENT_SECRET"),
        },
        form=True,
    )
    if not isinstance(payload, dict):
        # A null or non-object 200 body is the transient shape the
        # auth/discovery handler retries. Match fetch_otel and raise a
        # readable KeyError instead of an AttributeError off .get().
        raise KeyError("no access_token in the token response")
    token = payload.get("access_token")
    if not token:
        raise KeyError("no access_token in the token response")
    return str(token)


def discover_sessions(
    instance: str,
    headers: dict,
    window_days: int,
    limit: int,
    api_version: str,
) -> tuple:
    query = http_json(
        "GET",
        f"{instance}/services/data/{api_version}/query/?q={urllib.parse.quote(discovery_soql(window_days, limit))}",
        headers,
    )
    if not isinstance(query, dict):
        raise KeyError("no records in the query response")
    raw_records = query.get("records")
    records = raw_records if isinstance(raw_records, list) else []
    if any(not isinstance(record, dict) for record in records):
        raise KeyError("no records in the query response")
    return (
        [record for record in records if record.get("ssot__Id__c")],
        len(records),
    )


def fetch_otel(
    instance: str, headers: dict, session_id: str, api_version: str
) -> dict:
    payload = http_json(
        "GET",
        f"{instance}/services/data/{api_version}/einstein/audit/otel/{urllib.parse.quote(session_id, safe='')}",
        {**headers, "Accept": "application/json"},
    )
    if not isinstance(payload, dict):
        # A null or non-object 200 body is the transient shape the
        # auth/discovery handler retries. Do not record it as unreadable.
        raise KeyError("no resourceSpans in the OTel response body")
    return payload


def is_fatal_http(exc: BaseException) -> bool:
    if not isinstance(exc, urllib.error.HTTPError):
        return False
    if exc.code in (400, 404):
        return True
    if exc.code != 403:
        return False
    # Salesforce 401 is an expired token. 403 quota retries. These do not.
    body = getattr(exc, "hh_body", "")
    return "INSUFFICIENT_ACCESS" in body or "API_DISABLED_FOR_ORG" in body


def honeyhive_post_result(exc: BaseException) -> str:
    if not isinstance(exc, urllib.error.HTTPError):
        return "retry"
    # 401/403 is a bad key. 404 is a bad URL: hive-kube has no payload-specific
    # 404, so the path is wrong and every session would fail the same way.
    if exc.code in (401, 403, 404):
        return "auth"
    if exc.code == 400:
        return "reject"
    return "retry"


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
        # urlopen returned a 2xx. The spans stored; only the body did not
        # parse (a proxy or ingress answering 200 with non-JSON). Treating
        # this as retryable would re-POST an accepted payload every pass.
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


def main() -> None:
    instance = require("SALESFORCE_INSTANCE_URL").rstrip("/")
    if not instance.startswith("https://"):
        raise SystemExit(
            "SALESFORCE_INSTANCE_URL must start with https://, got "
            f"{instance!r}"
        )
    raw_dry_run = os.environ.get("DRY_RUN", "").strip().lower()
    if raw_dry_run not in ("", "0", "false", "no", "1", "true", "yes"):
        raise SystemExit(f"DRY_RUN must be 1 or 0, got {raw_dry_run!r}")
    dry_run = raw_dry_run in ("1", "true", "yes")
    hh_url = ""
    hh_key = ""
    if not dry_run:
        hh_url = require("HH_API_URL").rstrip("/")
        # A value without a scheme raises ValueError from urllib.request.Request,
        # which is not in FETCH_ERRORS and would end the poll loop.
        if not hh_url.startswith(("https://", "http://")):
            raise SystemExit(
                "HH_API_URL must start with https:// or http://, got "
                f"{hh_url!r}"
            )
        hh_key = require("HH_API_KEY")
    interval = env_int("POLL_INTERVAL", "60", minimum=1)
    max_passes = env_int("MAX_PASSES", "0", minimum=0)
    only = os.environ.get("SALESFORCE_SESSION_ID", "").strip()
    if only and only != urllib.parse.quote(only, safe=""):
        raise SystemExit(
            "SALESFORCE_SESSION_ID must be a bare session ID, got "
            f"{only!r}"
        )
    hh_override = os.environ.get("HONEYHIVE_SESSION_ID", "").strip()
    if hh_override:
        try:
            hh_override = str(uuid.UUID(hh_override))
        except ValueError:
            raise SystemExit("HONEYHIVE_SESSION_ID must be a UUID")
    window_days = env_int("DISCOVERY_WINDOW_DAYS", "4", minimum=0)
    discovery_limit = env_int("DISCOVERY_LIMIT", "20", minimum=1)
    idle_seconds = env_int("SESSION_IDLE_SECONDS", "120", minimum=1)
    api_version = (
        os.environ.get("SALESFORCE_API_VERSION", "").strip() or "v66.0"
    )
    if api_version != urllib.parse.quote(api_version, safe="."):
        raise SystemExit(
            "SALESFORCE_API_VERSION must not contain a path separator or a "
            f"character that needs URL-encoding, got {api_version!r}"
        )
    exported_file = (
        os.environ.get("EXPORTED_FILE", ".agentforce-exported.json").strip()
        or ".agentforce-exported.json"
    )
    exported, rejected, reject_reasons = (
        (set(), set(), {}) if dry_run else load_exported(exported_file)
    )
    if not dry_run:
        # Fail before the first POST, not after it. A restart on an unwritable
        # path would otherwise re-POST the same session on every cycle.
        save_exported(exported_file, exported, rejected, reject_reasons)
    passes = 0
    pin_once = True
    limit_warned = False
    expired_warned = False
    unparseable_start_warned: set[str] = set()
    starts: dict[str, str] = {}

    def reject(session_id: str, persist: bool, reason: str) -> None:
        reject_reasons[session_id] = reason
        mark_rejected(
            exported,
            rejected,
            reject_reasons,
            session_id,
            exported_file,
            persist,
            reason,
            starts.get(session_id, "unknown"),
        )

    def warn_expired_band_once() -> None:
        nonlocal expired_warned
        if expired_warned:
            return
        if window_days in (1, 2):
            # LAST_N_DAYS:1 and :2 stay inside 72 hours, so an expired reject
            # here means clock skew, not a dead band. No tuning advice applies.
            return
        expired_warned = True
        future = (
            "Lowering DISCOVERY_WINDOW_DAYS only affects future passes; "
            "IDs already recorded stay rejected"
        )
        if window_days == 0:
            print(
                "Expired sessions stay in discovery after Salesforce's "
                "72-hour OTel window. At DISCOVERY_WINDOW_DAYS=0 there is "
                "no time filter, so this band is unbounded. Set 3 to bound "
                f"it at 24 hours, unless the org rejected that literal. {future}"
            )
        elif window_days > 3:
            print(
                "Expired sessions stay in discovery after Salesforce's "
                "72-hour OTel window. 3 shrinks the band to at most 24 "
                "hours and still covers the full window; lower than 3 "
                f"drops sessions Salesforce would still export. {future}"
            )
        elif window_days == 3:
            print(
                "Expired sessions stay in discovery after Salesforce's "
                "72-hour OTel window. DISCOVERY_WINDOW_DAYS is already 3, "
                "so the band is at most 24 hours and still covers the "
                f"full window. {future}"
            )

    while True:
        try:
            token = salesforce_token(instance)
            sf_headers = {"Authorization": f"Bearer {token}"}
            if only:
                sessions = [{"ssot__Id__c": only}]
                discovered = 1
            else:
                sessions, discovered = discover_sessions(
                    instance,
                    sf_headers,
                    window_days,
                    discovery_limit,
                    api_version,
                )
        except FETCH_ERRORS as exc:
            print(f"Auth or discovery failed: {error_text(exc)}")
            if is_fatal_http(exc):
                if only:
                    raise SystemExit(
                        "Giving up: Salesforce rejected the token request. "
                        "Check SALESFORCE_CLIENT_ID, SALESFORCE_CLIENT_SECRET, "
                        "and the api scope, or whether API access is enabled "
                        "for the org. A 404 here usually means "
                        f"SALESFORCE_INSTANCE_URL is not the org's My Domain "
                        f"login host: GET {instance}/services/data/ should "
                        "list API versions"
                    )
                if getattr(exc, "code", None) == 403:
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
                    f"{api_version}. GET {instance}/services/data/ lists the "
                    "versions the org does support"
                )
            passes += 1
            if sleep_unless_done(passes, max_passes, interval):
                # sleep_unless_done returns True only when max_passes is set.
                # An unbounded run sleeps and loops instead of reaching here.
                if only and pin_once:
                    raise SystemExit(
                        f"Gave up on {only} after {passes} pass(es) "
                        "without exporting"
                    )
                raise SystemExit(
                    f"Stopped after {passes} pass(es); the last pass "
                    "could not authenticate or discover sessions"
                )
            continue

        starts = {
            str(record["ssot__Id__c"]): start_label(record)
            for record in sessions
            if record.get("ssot__Id__c")
        }
        pending = [
            record
            for record in sessions
            if (
                str(record["ssot__Id__c"]) not in exported
                and str(record["ssot__Id__c"]) not in rejected
            )
            or (only and pin_once)
        ]
        rejected_here = [
            str(record["ssot__Id__c"])
            for record in sessions
            if str(record["ssot__Id__c"]) in rejected
        ]
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
            print(
                "Rejected: "
                + ", ".join(
                    (
                        f"{sid} ({reject_reasons[sid]}, started "
                        f"{starts.get(sid, 'unknown')})"
                        if sid in reject_reasons
                        else f"{sid} (started {starts.get(sid, 'unknown')})"
                    )
                    for sid in rejected_here
                )
            )
        if not only and discovered >= discovery_limit and not limit_warned:
            limit_warned = True
            print(
                f"Hit DISCOVERY_LIMIT={discovery_limit}; older sessions in the "
                "window are not returned, and new conversations push the oldest "
                "out of this result. Raise DISCOVERY_LIMIT to reach the rest, "
                "while they are inside DISCOVERY_WINDOW_DAYS and Salesforce's "
                "72-hour export window"
            )
        for record in pending:
            session_id = str(record["ssot__Id__c"])
            try:
                payload = fetch_otel(
                    instance, sf_headers, session_id, api_version
                )
            except FETCH_ERRORS as exc:
                print(f"Skip {session_id}: {error_text(exc)}")
                if is_fatal_http(exc):
                    if getattr(exc, "code", None) in (400, 404):
                        if only:
                            raise SystemExit(
                                f"Giving up on {session_id}: Salesforce rejected the fetch. "
                                "Unknown session ID, or the session is past the 72-hour window, "
                                f"or the org does not support {api_version}. "
                                f"GET {instance}/services/data/ lists the versions "
                                "the org does support"
                            )
                        # A 404 during Data 360 provisioning can be transient.
                        # Record only after the 72-hour OTel window, like empty spans.
                        window_reason = otel_window_expired(
                            record, unparseable_start_warned
                        )
                        if not dry_run and window_reason:
                            reject(
                                session_id,
                                persist=True,
                                reason=window_reason,
                            )
                            if window_reason == "expired":
                                warn_expired_band_once()
                    else:
                        raise SystemExit(
                            "Giving up: Salesforce denied the OTel fetch. "
                            "Check that the ECA Run As user can read Einstein "
                            "Audit data (Setup > Einstein Audit, Analytics, and "
                            "Monitoring Setup), or whether API access is enabled "
                            "for the org"
                        )
                continue
            force = bool(only)
            try:
                count = len(collect_spans(payload))
                complete = force or session_is_complete(
                    record, payload, idle_seconds
                )
            except (AttributeError, TypeError, ValueError) as exc:
                print(f"Skip {session_id}: could not read payload: {exc}")
                if only:
                    raise SystemExit(
                        f"Giving up on {session_id}: payload could not be read"
                    )
                reject(
                    session_id,
                    persist=not dry_run,
                    reason="unreadable",
                )
                continue
            window_reason = (
                otel_window_expired(record, unparseable_start_warned)
                if count == 0
                else None
            )
            if not complete:
                if count == 0:
                    if window_reason == "expired":
                        print(
                            f"Skip {session_id}: no spans and the start "
                            "timestamp is past Salesforce's 72-hour OTel "
                            "window"
                        )
                        if not force and not dry_run:
                            reject(
                                session_id,
                                persist=True,
                                reason="expired",
                            )
                            warn_expired_band_once()
                    else:
                        print(
                            f"Skip {session_id}: no spans yet, Data 360 "
                            "join is still catching up"
                        )
                else:
                    print(f"Skip in-progress {session_id}")
                continue
            if count == 0:
                # missing_start on a pin is the synthetic row, not a Data 360
                # fact, so it is not evidence the payload will stay empty.
                if window_reason and not force:
                    print(f"Skip {session_id}: empty spans")
                else:
                    print(
                        f"Skip {session_id}: no spans yet, Data 360 "
                        "join is still catching up"
                    )
                if not force and not dry_run and window_reason:
                    reject(
                        session_id,
                        persist=True,
                        reason=(
                            "empty_missing_start"
                            if window_reason == "missing_start"
                            else window_reason
                        ),
                    )
                    if window_reason == "expired":
                        warn_expired_band_once()
                continue
            hh_session = honeyhive_session_id(session_id)
            if only and hh_override:
                hh_session = hh_override
            try:
                stamp_and_map(
                    payload, hh_session, session_name_for(payload, bool(only))
                )
            except (AttributeError, ValueError, TypeError, RecursionError) as exc:
                print(f"Skip {session_id}: could not map payload: {exc}")
                if only:
                    raise SystemExit(
                        f"Giving up on {session_id}: mapping failed"
                    )
                reject(
                    session_id,
                    persist=not dry_run,
                    reason="mapping",
                )
                continue
            result = try_export(
                payload,
                count,
                session_id,
                hh_session,
                dry_run,
                hh_url,
                hh_key,
                end_label(record),
            )
            if result == "auth":
                raise SystemExit(
                    f"HoneyHive rejected the export for {session_id}. "
                    "401 or 403: check HH_API_KEY. 404: check HH_API_URL - "
                    "the traces path is wrong, not the payload."
                )
            if result != "ok":
                if only and result == "reject":
                    raise SystemExit(
                        f"Giving up on {session_id}: HoneyHive POST failed"
                    )
                if result == "reject":
                    reject(
                        session_id,
                        persist=not dry_run,
                        reason="hh_400",
                    )
                continue
            mark_exported(
                exported,
                rejected,
                reject_reasons,
                session_id,
                exported_file,
                persist=not dry_run,
            )
            if only:
                pin_once = False
        passes += 1
        if only and not pin_once:
            break
        if sleep_unless_done(passes, max_passes, interval):
            if only and pin_once:
                raise SystemExit(
                    f"Gave up on {only} after {passes} pass(es) "
                    "without exporting"
                )
            break


if __name__ == "__main__":
    main()
