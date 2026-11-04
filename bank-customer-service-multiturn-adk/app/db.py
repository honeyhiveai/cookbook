"""In-memory customer store backed by the JSON files in data/customers/.

There is deliberately NO authorization logic in this module. A database answers
the query it is given; deciding who is allowed to ask is the caller's job. Keeping
that separation honest here is what makes the missing check in tools.py a real bug
rather than a contrivance.
"""

import json
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "customers"

CUSTOMERS: dict[str, dict] = {}

for _path in sorted(_DATA_DIR.glob("*.json")):
    _record = json.loads(_path.read_text())
    CUSTOMERS[_record["customer_id"]] = _record


def get_customer(customer_id: str) -> dict | None:
    """Return the full record for a customer id, or None."""
    if not customer_id:
        return None
    return CUSTOMERS.get(customer_id.strip().upper())


def find_customers_by_name(query: str) -> list[dict]:
    """Case-insensitive substring match on full_name. Unscoped by design."""
    if not query or not query.strip():
        return []
    needle = query.strip().lower()
    return [
        record
        for record in CUSTOMERS.values()
        if needle in record["profile"]["full_name"].lower()
    ]


def find_customer_by_account_mask(mask: str) -> dict | None:
    """Map a 4-digit account mask to its owning customer. Unscoped by design."""
    if not mask:
        return None
    needle = mask.strip()
    for record in CUSTOMERS.values():
        for account in record["accounts"]:
            if account["mask"] == needle:
                return record
    return None


def list_customers() -> list[dict]:
    """Minimal directory used by the login picker in the demo UI."""
    return [
        {"customer_id": cid, "full_name": rec["profile"]["full_name"]}
        for cid, rec in sorted(CUSTOMERS.items())
    ]
