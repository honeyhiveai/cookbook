# Dedicated / self-host deployments — `HH_API_URL` validation

Most code samples on docs.honeyhive.ai assume the customer's data lives at the multi-tenant default `https://api.dp1.us.honeyhive.ai`. Dedicated and self-host customers do **not** — and silently defaulting to the multi-tenant host means their spans either fail to land (auth rejected) or worse, leak into the wrong tenant.

> **Always validate `HH_API_URL` (or the equivalent SDK param) before declaring an instrumentation done.** This is a Phase 0 / Phase 2 check, not a "nice to have" — wrong URL is among the most common silent failures, and `200 OK` from the wrong host doesn't catch it.

## Phase 0 — Detect that the user is on a dedicated deployment

Signals (any one is enough):

- The user's existing code already passes `server_url=...` (Python) or `serverUrl: ...` (TS) with a non-default host.
- `HH_API_URL` (or `HONEYHIVE_SERVER_URL`) is set in their `.env`, deploy config, k8s manifest, or CI secrets.
- The user mentions a tenant name ("we're on the Nationwide deployment") or a custom hostname.
- Their HoneyHive UI lives at a non-default host (e.g. `<tenant>.app.honeyhive.ai`) — the API host typically mirrors it (`<tenant>.api.honeyhive.ai`).
- Their API key was minted from a non-default workspace — ask, don't guess.

Common shapes:

| Customer type | API host | UI host |
|---|---|---|
| **Default (multi-tenant SaaS)** | `https://api.dp1.us.honeyhive.ai` | `https://app.honeyhive.ai` |
| **Dedicated** (e.g. Nationwide) | `https://<tenant>.api.honeyhive.ai` | `https://<tenant>.app.honeyhive.ai` |
| **Self-host (BYOC / on-prem)** | whatever the customer chose; usually `https://honeyhive.<corp-domain>` or `https://honeyhive.internal` |
| **Internal staging / dev** | `https://api.staging.honeyhive.ai`, `https://api.testing-dp-1.honeyhive.ai`, `http://localhost:3000` | corresponding `app.*` |

If you cannot confidently determine the host from the user's code, environment, or stated context: **ask them**. Do not pick the default by inference.

## Wire it into each path

### Path A (Python SDK)

```python
import os
from honeyhive import HoneyHiveTracer

tracer = HoneyHiveTracer.init(
    api_key=os.getenv("HH_API_KEY"),
    project=os.getenv("HH_PROJECT"),
    server_url=os.getenv("HH_API_URL"),  # required for dedicated / self-host
    session_name="my-app",
    source=os.getenv("HH_SOURCE", "dev"),
)
```

The SDK does **not** auto-read `HH_API_URL` from the environment — `server_url` defaults to the multi-tenant `https://api.dp1.us.honeyhive.ai` if you don't pass it. Pass it explicitly. Document the env var in the user's setup block.

### Path B (TypeScript SDK)

```typescript
import { HoneyHiveTracer } from "honeyhive";

const tracer = await HoneyHiveTracer.init({
  apiKey: process.env.HH_API_KEY!,
  project: process.env.HH_PROJECT!,
  serverUrl: process.env.HH_API_URL,  // optional: TS SDK auto-reads HH_API_URL when omitted
  sessionName: "my-app",
  source: "dev",
});
```

The TS SDK's `serverUrl` resolution chain is `params.serverUrl || process.env.HH_API_URL || DEFAULT_PROPERTIES.serverUrl` — so omitting `serverUrl` and relying on the env var works. **Pass it explicitly anyway** for grep-ability and to match the Python pattern.

For `@honeyhive/api-client` (manual session/event construction), the `Client` constructor takes the server URL the same way:

```typescript
import { Client } from "@honeyhive/api-client";

const client = new Client({
  apiKey: process.env.HH_API_KEY!,
  baseUrl: process.env.HH_API_URL,  // dedicated / self-host customers must set this
});
```

### Path C (native OTEL exporter)

Substitute the user's deployment host into the OTLP endpoint:

```yaml
exporters:
  otlphttp/honeyhive:
    endpoint: ${env:HH_API_URL}/opentelemetry/v1/traces
    headers:
      Authorization: "Bearer ${env:HH_API_KEY}"
```

Default `${env:HH_API_URL}` to `https://api.dp1.us.honeyhive.ai` only if the user has confirmed they're on the multi-tenant host. The OTLP endpoint is **always** `<HH_API_URL>/opentelemetry/v1/traces` — same suffix on every deployment.

## Phase 2 — Verify the URL works before declaring success

Before the smoke run, sanity-check the URL:

```bash
# Reachability + auth sanity (replace the URL):
curl -sS -o /dev/null -w "HTTP %{http_code}\n" \
  -H "Authorization: Bearer $HH_API_KEY" \
  "$HH_API_URL/projects"
# Expect: HTTP 200. HTTP 401 = wrong API key for this deployment. HTTP 404 / 000 = wrong host.
```

If the user has `HH_API_URL` pointing at a dedicated tenant but a project API key minted from the public workspace (or vice versa), the sanity-check returns 401 — surface this immediately rather than discovering it after a failed smoke run.

For self-host, also verify cert chain:

```bash
curl -v "$HH_API_URL/projects" 2>&1 | grep -E 'SSL|TLS|verify'
# If "self signed certificate" or "unable to get local issuer certificate" appears, the
# user's runtime needs a custom CA bundle (REQUESTS_CA_BUNDLE for Python, NODE_EXTRA_CA_CERTS
# for Node, or the OTel collector's tls.ca_file). See references/prod-gotchas.md §7.
```

## Common failure modes (Dedicated / Self-host)

- **Spans returning 401 or 403.** API key was minted on a different deployment than `HH_API_URL` points at. Verify both came from the same workspace UI.
- **Spans silently dropping with no error.** The SDK defaulted to `https://api.dp1.us.honeyhive.ai` because `server_url` / `serverUrl` was not passed. The multi-tenant host accepts the request shape but rejects auth — sometimes silently if the user's pipeline swallows non-2xx. Always pass the URL explicitly.
- **Spans landing in the wrong tenant.** A dedicated customer copy-pasted a multi-tenant code sample without changing the URL. Their key works on both (they have a multi-tenant API key too for testing), so spans appear "in HoneyHive" but in the wrong workspace. Grep for hardcoded `https://api.dp1.us.honeyhive.ai` (or the older `https://api.honeyhive.ai`) in any code you didn't author.
- **TLS errors against `<tenant>.api.honeyhive.ai`.** Self-host deployments may pin a custom CA. See `references/prod-gotchas.md` §7.
- **OTel collector silently exporting to default.** OTTL processors only set attributes; the OTLP exporter `endpoint:` field doesn't honor `HH_API_URL` automatically. Substitute it via `${env:HH_API_URL}/opentelemetry/v1/traces` or hardcode the customer's host in the collector config.

## Hard rule

**Never declare an instrumentation complete without confirming `HH_API_URL` / `server_url` / `serverUrl` is set to the customer's actual deployment.** "It looked right in dev" is not validation — `curl` against the URL with their key.
