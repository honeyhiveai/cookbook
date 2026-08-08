"""Bridge ACS runtime decisions into HoneyHive spans.

Microsoft's Agent Control Specification (ACS) is the runtime-enforcement layer
of the "open trust stack": evaluate (ASSERT) -> enforce (ACS) -> observe
(HoneyHive). Every ACS guard helper in the Python SDK -- ``run``, ``run_tool``,
``protect_tool``, ``enforce``, the lifecycle seams, and the ``guard_*`` framework
adapters -- funnels through one method:

    AgentControl.evaluate_intervention_point(intervention_point, snapshot, mode)

This module turns each of those evaluations into a HoneyHive span carrying the
decision, reason, identity, and the transformed policy target as queryable
metadata / metrics / outputs.

Two surfaces are provided:

  * :func:`make_acs_guard` -- the simple, explicit manual wrapper. One ACS
    evaluation -> one HoneyHive span. Use it to understand the mapping.

  * :func:`instrument_acs` -- the recommended "easy mode". It monkeypatches
    ``AgentControl.evaluate_intervention_point`` so that ALL ACS activity is
    auto-captured as HoneyHive spans with ZERO changes to agent/host code.
"""
from __future__ import annotations

from typing import Any, Mapping, Optional

from agent_control_specification import (
    AgentControl,
    Decision,
    EnforcementMode,
    InterventionPoint,
)
from honeyhive import atrace, enrich_span

_INSTRUMENTED_FLAG = "_acs_honeyhive_instrumented"


def _intervention_point_value(intervention_point: Any) -> str:
    if isinstance(intervention_point, InterventionPoint):
        return intervention_point.value
    return str(intervention_point)


def _enrich_from_result(intervention_point: Any, result: Any) -> None:
    """Attach ACS decision detail to the currently active HoneyHive span."""
    verdict = result.verdict
    decision = verdict.decision
    ip_value = _intervention_point_value(intervention_point)
    enrich_span(
        metadata={
            "acs.intervention_point": ip_value,
            "acs.decision": decision.value,
            "acs.reason": verdict.reason,
            "acs.message": verdict.message,
            "acs.input_identity": result.input_identity,
            "acs.enforced_identity": result.enforced_identity,
        },
        metrics={
            "acs_allowed": 1 if decision == Decision.ALLOW else 0,
            "acs_warned": 1 if decision == Decision.WARN else 0,
            "acs_denied": 1 if decision == Decision.DENY else 0,
            "acs_escalated": 1 if decision == Decision.ESCALATE else 0,
            "acs_transformed": 1 if decision == Decision.TRANSFORM else 0,
        },
        outputs={
            "decision": decision.value,
            "reason": verdict.reason,
            "message": verdict.message,
            "transformed_policy_target": result.transformed_policy_target,
        },
    )


def make_acs_guard(control: AgentControl, *, event_type: str = "tool"):
    """Return an explicit, traced wrapper around one ACS evaluation.

    This is the "for understanding" surface from the cookbook: each call emits
    exactly one HoneyHive span with the decision detail. Prefer
    :func:`instrument_acs` for real hosts so existing guard helpers are covered
    automatically.
    """

    @atrace(event_type=event_type, event_name="acs.guard")
    async def acs_guard(
        intervention_point: InterventionPoint,
        snapshot: Mapping[str, Any],
        mode: EnforcementMode | str = EnforcementMode.ENFORCE,
    ):
        result = await control.evaluate_intervention_point(intervention_point, snapshot, mode)
        _enrich_from_result(intervention_point, result)
        return result

    return acs_guard


def instrument_acs(tracer: Optional[Any] = None, *, event_type: str = "tool") -> None:
    """Auto-capture every ACS evaluation as a HoneyHive span.

    Monkeypatches :meth:`AgentControl.evaluate_intervention_point`. Because every
    SDK guard helper routes through that method, this captures ALL ACS activity
    (lifecycle, model, tool, input/output points, and framework adapters) with no
    changes to agent or host code.

    Idempotent: calling it more than once is a no-op. ``tracer`` is accepted for
    API symmetry with the rest of the cookbook; the HoneyHive decorators resolve
    the active tracer/span from context, so it is not required.
    """
    if getattr(AgentControl, _INSTRUMENTED_FLAG, False):
        return

    original_evaluate = AgentControl.evaluate_intervention_point

    @atrace(event_type=event_type, event_name="acs.guard")
    async def _traced_evaluate(
        self: AgentControl,
        intervention_point: InterventionPoint | str,
        snapshot: Mapping[str, Any],
        mode: EnforcementMode | str = EnforcementMode.ENFORCE,
    ):
        result = await original_evaluate(self, intervention_point, snapshot, mode)
        ip_value = _intervention_point_value(intervention_point)
        # Keep auto-captured inputs clean (the wrapper also receives ``self``).
        enrich_span(inputs={"intervention_point": ip_value, "snapshot": dict(snapshot)})
        _enrich_from_result(intervention_point, result)
        return result

    AgentControl.evaluate_intervention_point = _traced_evaluate
    setattr(AgentControl, _INSTRUMENTED_FLAG, True)
    setattr(AgentControl, "_acs_honeyhive_original_evaluate", original_evaluate)


def uninstrument_acs() -> None:
    """Restore the original ``evaluate_intervention_point`` (useful in tests)."""
    original = getattr(AgentControl, "_acs_honeyhive_original_evaluate", None)
    if original is not None:
        AgentControl.evaluate_intervention_point = original
        delattr(AgentControl, "_acs_honeyhive_original_evaluate")
    setattr(AgentControl, _INSTRUMENTED_FLAG, False)
