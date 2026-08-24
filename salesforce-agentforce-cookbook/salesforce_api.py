"""Salesforce token, session discovery, and Session Trace OTel fetch."""

from __future__ import annotations

import urllib.parse

from config import require
from net import as_object, http_json


def discovery_soql(window_days: int, limit: int) -> str:
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
    token = as_object(payload, "no access_token in the token response").get(
        "access_token"
    )
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
    raw_records = as_object(query, "no records in the query response").get("records")
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
    return as_object(payload, "no resourceSpans in the OTel response body")
