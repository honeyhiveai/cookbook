"""Stamp public OTel / OpenInference attributes onto Salesforce Session Trace OTel.

Salesforce Session Trace does not emit HoneyHive-ready I/O. Turn spans use dotted
`agent.messages.{role}.{n}.content` keys. Step spans put I/O in a non-standard
`input.value` / `output.value` kvlist object map, sometimes with nested
`gen_ai.input.messages`. This module groups one conversation as one session,
sets an OpenInference span kind, and rewrites I/O onto GenAI / OpenInference
JSON strings.

Public contract:
https://docs.honeyhive.ai/v2/sdk-reference/semconv-alignment
https://opentelemetry.io/docs/specs/semconv/gen-ai/
https://github.com/Arize-ai/openinference/blob/main/spec/semantic_conventions.md
"""

from __future__ import annotations

import html
import json
import uuid

LLM_STEPS = {
    "LLM_STEP",
    "CLASSIFIER_STEP",
    "TOPIC_STEP",
    "TRUST_GUARDRAILS_STEP",
}
TOOL_STEPS = {"VARIABLE_UPDATE_STEP"}
LLM_NAMES = {
    "agent_router",
    "pre_orchestration.guardrail",
    "InstructionAdherence",
}


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
        return [
            any_value(item) if isinstance(item, dict) else unescape(item)
            for item in items
        ]
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


def honeyhive_session_id(sf_session_id: str) -> str:
    # Salesforce session ids are already UUIDs. Reusing them as the HoneyHive
    # session_id makes the Traces session page open a child turn instead of
    # the conversation. Derive a distinct id.
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"agentforce:{sf_session_id}"))


def replace_or_add(items: list, key: str, value) -> None:
    encoded = attr(key, value)
    for item in items:
        if item.get("key") == key:
            item["value"] = encoded["value"]
            return
    items.append(encoded)


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


def maybe_json(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


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


def map_io(attrs: dict) -> tuple[list, dict, str | None]:
    chat_history: list = []
    outputs: dict = {}
    model = None

    in_val = maybe_json(attrs.get("input.value"))
    out_val = maybe_json(attrs.get("output.value"))

    if isinstance(in_val, dict):
        if in_val.get("gen_ai.request.model"):
            model = str(in_val["gen_ai.request.model"])
        chat_history = as_messages(in_val.get("gen_ai.input.messages"))
        if not chat_history and in_val.get("classifier.input"):
            text = message_text(in_val["classifier.input"])
            if text:
                chat_history = [{"role": "user", "content": text}]
    elif isinstance(in_val, str) and in_val:
        chat_history = [{"role": "user", "content": in_val}]

    if not chat_history and attrs.get("gen_ai.input.messages") is not None:
        chat_history = as_messages(attrs.get("gen_ai.input.messages"))

    if isinstance(out_val, dict):
        raw_out = out_val.get("gen_ai.output.messages")
        if isinstance(raw_out, str) and raw_out.strip():
            outputs = {"role": "assistant", "content": raw_out}
        else:
            out_messages = as_messages(raw_out)
            content = last_content(out_messages, ("assistant", "model", "Output"))
            if not content:
                content = message_text(raw_out)
            if not content:
                content = message_text(
                    out_val.get("af.router_classifier.selected_target")
                ) or message_text(out_val.get("mgr.sensitive.step.result"))
            if content:
                outputs = {"role": "assistant", "content": content}
        if not model and out_val.get("gen_ai.request.model"):
            model = str(out_val["gen_ai.request.model"])
    elif isinstance(out_val, str) and out_val:
        outputs = {"role": "assistant", "content": out_val}

    if not outputs.get("content") and attrs.get("gen_ai.output.messages") is not None:
        raw_out = attrs.get("gen_ai.output.messages")
        if isinstance(raw_out, str) and raw_out.strip() and not raw_out.lstrip().startswith(("[", "{")):
            outputs = {"role": "assistant", "content": raw_out}
        else:
            out_messages = as_messages(raw_out)
            content = last_content(out_messages, ("assistant", "model", "Output")) or message_text(
                raw_out
            )
            if content:
                outputs = {"role": "assistant", "content": content}

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
        if not chat_history:
            chat_history.extend({"role": role, "content": text} for _, role, text in indexed)
        if not outputs.get("content"):
            for _, role, text in reversed(indexed):
                if role == "assistant":
                    outputs = {"role": "assistant", "content": text}
                    break

    if not model and attrs.get("gen_ai.request.model"):
        model = str(attrs["gen_ai.request.model"])
    return chat_history, outputs, model


def rewrite_io(items: list, attrs: dict, kind: str) -> None:
    # CHAIN (turn) spans must not get OpenInference input.value. HoneyHive keeps
    # that attribute as a raw string on chain events, which hides the messages.
    chat_history, outputs, model = map_io(attrs)
    if kind == "TOOL":
        return
    if chat_history:
        replace_or_add(items, "gen_ai.input.messages", json.dumps(chat_history, default=str))
        if kind == "LLM":
            payload: dict = {"messages": chat_history}
            if model:
                payload["model"] = model
            replace_or_add(items, "input.value", json.dumps(payload, default=str))
    if outputs.get("content"):
        out_messages = [
            {"role": outputs.get("role") or "assistant", "content": outputs["content"]}
        ]
        replace_or_add(items, "gen_ai.output.messages", json.dumps(out_messages, default=str))
        if kind == "LLM":
            replace_or_add(items, "output.value", json.dumps(outputs, default=str))
    if model:
        replace_or_add(items, "gen_ai.request.model", model)


def openinference_span_kind(span: dict, attrs: dict) -> str:
    step_type = str(attrs.get("step.type") or "")
    name = span.get("name") or ""
    if step_type in LLM_STEPS or name in LLM_NAMES:
        return "LLM"
    if name == "__state_update_action__" or step_type in TOOL_STEPS:
        return "TOOL"
    return "CHAIN"


def _resource_attrs(resource: dict) -> list:
    if not isinstance(resource, dict):
        return []
    items = resource.get("attributes")
    if not isinstance(items, list):
        items = []
        resource["attributes"] = items
    return items


def _span_attrs(span: dict) -> list:
    items = span.get("attributes")
    if not isinstance(items, list):
        items = []
        span["attributes"] = items
    return items


def stamp_and_map(payload: dict, hh_session_id: str, session_name: str) -> None:
    for resource_wrap in payload.get("resourceSpans") or []:
        resource = resource_wrap.get("resource")
        if not isinstance(resource, dict):
            resource = {}
            resource_wrap["resource"] = resource
        resource_attrs = _resource_attrs(resource)
        flatten_attributes(resource_attrs)
        # HoneyHive creates the session row from this flag. Without it, a
        # child span can show up as the session in the UI.
        replace_or_add(resource_attrs, "honeyhive.session_id", hh_session_id)
        replace_or_add(resource_attrs, "honeyhive.session_auto_create", True)
        replace_or_add(resource_attrs, "gen_ai.conversation.id", hh_session_id)
        if session_name:
            replace_or_add(resource_attrs, "honeyhive.session_name", session_name)
            replace_or_add(resource_attrs, "gen_ai.agent.name", session_name)
        for scope in resource_wrap.get("scopeSpans") or []:
            for span in scope.get("spans") or []:
                items = _span_attrs(span)
                decoded = span_attr_map(items)
                flatten_attributes(items)
                replace_or_add(items, "honeyhive.session_id", hh_session_id)
                replace_or_add(items, "honeyhive.session_auto_create", True)
                replace_or_add(items, "gen_ai.conversation.id", hh_session_id)
                if session_name:
                    replace_or_add(items, "honeyhive.session_name", session_name)
                kind = openinference_span_kind(span, decoded)
                replace_or_add(items, "openinference.span.kind", kind)
                rewrite_io(items, decoded, kind)


def session_name_for(payload: dict, override: str | None) -> str:
    if override:
        return override
    for resource_wrap in payload.get("resourceSpans") or []:
        mapped = span_attr_map(
            ((resource_wrap.get("resource") or {}).get("attributes")) or []
        )
        agent = mapped.get("session.actors.0.name") or mapped.get("gen_ai.agent.name")
        if agent:
            return str(agent)
    return "Agentforce"
