"""Stamp public OTel / OpenInference attributes onto Salesforce Session Trace OTel.

Salesforce already emits GenAI-shaped fields (`gen_ai.input.messages`,
`gen_ai.request.model`, and similar). This module does not rewrite those onto
HoneyHive backend buckets. It only groups one conversation as one session and
sets an OpenInference span kind.

Public contract:
https://docs.honeyhive.ai/v2/sdk-reference/semconv-alignment
https://opentelemetry.io/docs/specs/semconv/gen-ai/
https://github.com/Arize-ai/openinference/blob/main/spec/semantic_conventions.md
"""

from __future__ import annotations

import html
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
                replace_or_add(items, "honeyhive.session_id", hh_session_id)
                replace_or_add(items, "honeyhive.session_auto_create", True)
                replace_or_add(items, "gen_ai.conversation.id", hh_session_id)
                if session_name:
                    replace_or_add(items, "honeyhive.session_name", session_name)
                kind = openinference_span_kind(span, span_attr_map(items))
                replace_or_add(items, "openinference.span.kind", kind)


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
