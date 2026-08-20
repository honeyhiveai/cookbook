"""Optional guarded mode — the "and here's the fix" slide. Off by default.

Verified ADK contract: a before_tool_callback that returns a dict BLOCKS the
tool (the body never runs and the returned dict becomes the function response the
model sees). Returning None allows the call through.

Correction to the build spec: the spec's snippet only inspects a `customer_id`
argument. That leaves lookup_account_by_mask and lookup_customer_by_name
unguarded, so attack turns 1 and 3 still disclose another customer's data with
the guardrail ON — which would break the very before/after contrast guarded mode
exists to show. Those two tools take a lookup key rather than an id, so the
callback resolves the key to its owner before deciding.

Note for the narration: this is where enforcement lives. HoneyHive's online
evaluators are asynchronous and post-ingestion — they detect, they cannot block.
"""

import logging

from app import db

logger = logging.getLogger(__name__)

DENIED = {
    "status": "error",
    "error_message": "Access denied: this record belongs to a different customer.",
}


def _norm(value) -> str:
    return str(value).strip().upper()


def _resolve_owners(args: dict) -> list[str]:
    """Owner ids this call would reach, resolved from whichever key it uses."""
    if args.get("customer_id"):
        return [_norm(args["customer_id"])]

    if args.get("mask"):
        record = db.find_customer_by_account_mask(args["mask"])
        return [record["customer_id"]] if record else []

    if args.get("name"):
        return [r["customer_id"] for r in db.find_customers_by_name(args["name"])]

    return []


def enforce_customer_scope(tool, args, tool_context):
    """Block any tool call that would reach a customer other than the authenticated one."""
    auth = tool_context.state.get("authenticated_customer_id")
    if not auth:
        return None

    args = args or {}
    owners = _resolve_owners(args)
    foreign = [o for o in owners if o and o != _norm(auth)]

    if not foreign:
        return None

    requested = (
        args.get("customer_id") or args.get("mask") or args.get("name") or ""
    )

    try:
        from honeyhive import enrich_span

        enrich_span(
            metadata={
                "access_check": True,
                "tool_name": getattr(tool, "name", str(tool)),
                "authenticated_customer_id": auth,
                "requested_key": str(requested),
                # what the call WOULD have reached; nothing was returned
                "record_owner_id": foreign if len(foreign) > 1 else foreign[0],
                "record_owner_name": None,
                "records_returned": 0,
                "fields_returned": [],
                "pii_fields_returned": [],
                "blocked_by_guardrail": True,
            },
            user_properties={"user_id": auth},
        )
    except Exception:
        logger.debug("enrich_span unavailable in guardrail", exc_info=True)

    return DENIED
