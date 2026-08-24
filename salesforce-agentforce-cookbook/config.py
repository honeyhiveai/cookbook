"""Read poller settings from the environment."""

from __future__ import annotations

import os
import urllib.parse
import uuid
from dataclasses import dataclass


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


@dataclass(frozen=True)
class Settings:
    instance: str
    dry_run: bool
    hh_url: str
    hh_key: str
    interval: int
    max_passes: int
    only: str
    hh_override: str
    session_name_override: str
    window_days: int
    discovery_limit: int
    idle_seconds: int
    api_version: str
    exported_file: str

    @property
    def persist(self) -> bool:
        return not self.dry_run


def load_settings() -> Settings:
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
        if not hh_url.startswith(("https://", "http://")):
            raise SystemExit(
                "HH_API_URL must start with https:// or http://, got "
                f"{hh_url!r}"
            )
        hh_key = require("HH_API_KEY")
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
    return Settings(
        instance=instance,
        dry_run=dry_run,
        hh_url=hh_url,
        hh_key=hh_key,
        interval=env_int("POLL_INTERVAL", "60", minimum=1),
        max_passes=env_int("MAX_PASSES", "0", minimum=0),
        only=only,
        hh_override=hh_override,
        session_name_override=os.environ.get("HONEYHIVE_SESSION_NAME", "").strip(),
        window_days=env_int("DISCOVERY_WINDOW_DAYS", "4", minimum=0),
        discovery_limit=env_int("DISCOVERY_LIMIT", "20", minimum=1),
        idle_seconds=env_int("SESSION_IDLE_SECONDS", "120", minimum=1),
        api_version=api_version,
        exported_file=exported_file,
    )
