"""Custom ACS annotator dispatcher for the bank_agent manifest.

Two of the bank_agent Rego rules read derived classifier signals rather than
raw snapshot fields:

  * ``input_verdict``        -> ``annotations.prompt_classifier.risk_score``
  * ``pre_model_call_verdict`` -> ``annotations.model_request_classifier.contains_large_transfer``

In production those annotations come from `classifier` annotator *endpoints*
declared in the manifest. To keep this cookbook runnable with zero network
calls, we supply a host-owned annotator dispatcher (the Python protocol the
native runtime invokes synchronously). It implements a tiny, deterministic
heuristic classifier so every intervention point can fire its interesting
branch.

The dispatcher returns the value stored under ``annotations.<annotator_name>``
in the policy input the Rego policy sees. The shapes mirror the canonical
fixtures in the upstream example's ``policy_input/*.canonical.json``.
"""
from __future__ import annotations

import json
import re
from typing import Any, Mapping

# Keywords that push the prompt risk classifier over the deny threshold (>= 0.95).
_HIGH_RISK_PROMPT_PATTERNS = (
    "ignore previous",
    "ignore all previous",
    "bypass approval",
    "without approval",
    "disable the guardrail",
    "exfiltrate",
    "wire everything",
    "drain the account",
)

_LARGE_TRANSFER_PATTERN = re.compile(r"\$?\s*([0-9][0-9,]{3,})")
_LARGE_TRANSFER_THRESHOLD = 10_000


def _policy_target_value(preliminary_policy_input: Mapping[str, Any]) -> Any:
    target = preliminary_policy_input.get("policy_target") or {}
    return target.get("value")


def _as_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, default=str)


def _max_number_in(text: str) -> int:
    best = 0
    for match in _LARGE_TRANSFER_PATTERN.findall(text):
        try:
            best = max(best, int(match.replace(",", "")))
        except ValueError:
            continue
    return best


class BankClassifierAnnotator:
    """Deterministic, offline stand-in for the manifest's `classifier` annotators.

    Implements the ``AnnotatorDispatcher`` protocol
    (``agent_control_specification.AnnotatorDispatcher``): the native runtime
    calls :meth:`dispatch` once per annotation declared on the active
    intervention point, and stores the return value under
    ``annotations.<annotator_name>`` in the policy input.
    """

    def dispatch(
        self,
        annotator_name: str,
        annotator_config: Mapping[str, Any],
        preliminary_policy_input: Mapping[str, Any],
    ) -> Any:
        target = _policy_target_value(preliminary_policy_input)

        if annotator_name == "prompt_classifier":
            return self._classify_prompt(target)
        if annotator_name == "model_request_classifier":
            return self._classify_model_request(target)
        if annotator_name == "model_response_classifier":
            return self._classify_model_response(target)

        # The remaining annotators are declared in the manifest for parity with
        # the upstream example, but the corresponding Rego rules read the
        # snapshot directly, so benign canned values are sufficient.
        return {"labels": [], "risk_score": 0.0, "annotator": annotator_name}

    def _classify_prompt(self, target: Any) -> dict[str, Any]:
        text = ""
        if isinstance(target, Mapping):
            text = str(target.get("text", ""))
        elif isinstance(target, str):
            text = target
        lowered = text.lower()
        high_risk = any(pattern in lowered for pattern in _HIGH_RISK_PROMPT_PATTERNS)
        risk_score = 0.97 if high_risk else 0.42
        labels = ["finance_intent"]
        if high_risk:
            labels.append("prompt_injection")
        elif _max_number_in(text) >= _LARGE_TRANSFER_THRESHOLD:
            labels.append("large_transfer")
        return {"labels": labels, "risk_score": risk_score}

    def _classify_model_request(self, target: Any) -> dict[str, Any]:
        messages: list[Any] = []
        if isinstance(target, Mapping):
            raw = target.get("messages")
            if isinstance(raw, list):
                messages = raw
        elif isinstance(target, list):
            messages = target
        joined = " ".join(_as_text(m) for m in messages)
        contains_large_transfer = _max_number_in(joined) >= _LARGE_TRANSFER_THRESHOLD
        labels = ["tool_instruction"]
        if contains_large_transfer:
            labels.append("large_transfer")
        return {
            "labels": labels,
            "risk_score": 0.4 if contains_large_transfer else 0.1,
            "contains_large_transfer": contains_large_transfer,
        }

    def _classify_model_response(self, target: Any) -> dict[str, Any]:
        content = ""
        if isinstance(target, Mapping):
            message = target.get("message")
            if isinstance(message, Mapping):
                content = str(message.get("content", ""))
            else:
                content = str(target.get("content", ""))
        elif isinstance(target, str):
            content = target
        contains_bypass = "bypass approval" in content.lower()
        return {
            "labels": ["tool_plan"],
            "risk_score": 0.6 if contains_bypass else 0.25,
            "contains_approval_bypass": contains_bypass,
        }
