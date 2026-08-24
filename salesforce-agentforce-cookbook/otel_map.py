"""Map Salesforce Session Trace OTel onto HoneyHive session stamps."""

from __future__ import annotations

import html
import json
import uuid
from dataclasses import dataclass


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
    parsed = maybe_json(value)
    if isinstance(parsed, (dict, list)):
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
        if not chat_history:
            chat_history.extend(
                {"role": role, "content": text} for _, role, text in indexed
            )
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


@dataclass
class MappedSpan:
    event_type: str
    inputs: dict
    outputs: dict
    config: dict
    input_payload: object | None
    output_payload: object | None


def prepare(span: dict, raw: dict) -> MappedSpan:
    inputs, outputs, config = map_io(raw)
    event_type = event_type_for(span, raw)
    input_payload = None
    output_payload = None
    if event_type == "model":
        input_payload, output_payload = openinference_values(raw, inputs, outputs, config)
    else:
        leftover_in = leftover_bucket(raw.get("input.value"))
        if not inputs and leftover_in is not None:
            inputs["value"] = leftover_in
        leftover_out = leftover_bucket(raw.get("output.value"))
        if not outputs and leftover_out is not None:
            outputs["value"] = leftover_out
    return MappedSpan(
        event_type=event_type,
        inputs=inputs,
        outputs=outputs,
        config=config,
        input_payload=input_payload,
        output_payload=output_payload,
    )


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


def apply_mapped(span: dict, mapped: MappedSpan) -> None:
    items = span.get("attributes")
    if not isinstance(items, list):
        items = []
        span["attributes"] = items
    flatten_attributes(items)
    if mapped.event_type == "model":
        if mapped.input_payload is not None:
            replace_or_add(items, "input.value", json.dumps(mapped.input_payload, default=str))
        if mapped.output_payload is not None:
            replace_or_add(items, "output.value", json.dumps(mapped.output_payload, default=str))
    else:
        drop_keys(items, {"input.value", "output.value"})
    additions = [attr("honeyhive_event_type", mapped.event_type)]
    set_prefixed(additions, "honeyhive_inputs", mapped.inputs)
    set_prefixed(additions, "honeyhive_outputs", mapped.outputs)
    set_prefixed(additions, "honeyhive_config", mapped.config)
    items.extend(additions)


def map_span(span: dict) -> None:
    items = span.get("attributes")
    if not isinstance(items, list):
        items = []
        span["attributes"] = items
    apply_mapped(span, prepare(span, span_attr_map(items)))


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
                map_span(span)
                stamp_session(span_attrs, hh_session_id, session_name)
                drop_keys(span_attrs, {"gen_ai.agent.name", "agent_name"})


def session_name_for(payload: dict, override: str | None) -> str:
    if override:
        return override
    for resource in payload.get("resourceSpans") or []:
        mapped = span_attr_map((resource.get("resource") or {}).get("attributes"))
        agent = mapped.get("session.actors.0.name") or mapped.get("gen_ai.agent.name")
        if agent:
            return str(agent)
    return "Agentforce"
