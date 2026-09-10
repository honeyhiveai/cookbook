---
name: honeyhive-cli
description: >
  HoneyHive CLI install, discovery, and usage reference. Shared by
  honeyhive-instrument, honeyhive-evaluate, and honeyhive-improve skills.
  Use to install the CLI, discover commands, inspect schemas, and file
  doc-gap issues.
license: MIT
metadata:
  version: "0.1.0"
  homepage: https://docs.honeyhive.ai
---

# HoneyHive CLI

## Install

- **macOS:** `brew tap honeyhiveai/tap && brew install honeyhive`
- **Linux / CI / WSL:** `curl -fsSL https://github.com/honeyhiveai/honeyhive-cli/releases/latest/download/install.sh | sh` (requires glibc — works on Ubuntu, Debian, Fedora, RHEL, WSL; does **not** work on Alpine/musl)

## Discovery

- `honeyhive --help` — top-level namespaces and global flags
- `honeyhive <namespace> --help` — subcommands (e.g. `honeyhive events --help`)

## Schema Introspection

When a command accepts file input or structured arguments:

- `honeyhive <command> --show-file-schema` — JSON schema for file-based input
- `honeyhive <command> --show-argument-schema <argument-name>` — JSON schema for a specific structured argument (use the argument name without the `--` prefix)

Use these instead of guessing flags or payload shapes.

## Sanity Check

Before any skill that depends on HoneyHive, confirm the CLI is working and credentials are valid. Run these checks in order; stop on first failure.

1. **CLI installed?** `honeyhive --help` must succeed. If not, install per the instructions above.
2. **Env vars set?** `HH_API_KEY` and `HH_DATA_PLANE_URL` must be in the environment (never hardcoded in source). If missing, direct the user to their project settings page to find both values: `https://app.us.honeyhive.ai/settings/project/keys` for multi-tenant, or `https://app.<tenant>.us.honeyhive.ai/settings/project/keys` for dedicated deployments (see [references/dedicated-deployments.md](references/dedicated-deployments.md)).
3. **API reachable?** Run a single authenticated probe:
   ```bash
   honeyhive events search --filters '[]' --limit 1 --page 1
   ```
   A valid JSON response (array or `{"events":[...]}`) = good. An error or auth failure = stop and surface. If the CLI is not installed, fall back to curl — see [references/network-validation.md](references/network-validation.md) for the exact command and status-code table.
On failure at any step, surface the exact error and stop. Do not proceed into skill-specific work with broken credentials or connectivity.

The sanity check produces: `status` (pass/fail), `hh_data_plane_url`, `deployment_type`, and `probe_method`. The **calling skill** decides whether and where to persist these (e.g. `honeyhive-instrument` writes `state/network-validation.json`; other skills may not need state files).

## Doc-Gap Filing

When a skill hits missing CLI coverage, incomplete docs, or an unsupported framework/integration, file automatically:

```bash
gh issue create --repo honeyhiveai/skills \
  --title "Doc gap: <short description>" \
  --body "**Skill:** <skill-name>
**CLI/SDK version:** <detected version>
**Framework:** <framework and version>
**Gap:** <what is missing>
**Workaround:** <what was done instead>"
```

Report the created issue URL to the user.
