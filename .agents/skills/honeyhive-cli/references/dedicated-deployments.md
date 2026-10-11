# Dedicated / self-host deployments

Most code samples assume the multi-tenant default `https://api.dp1.us.honeyhive.ai`. Dedicated and self-host customers have their own host — silently defaulting to multi-tenant means spans fail auth.

## Detecting the deployment type

Signals (any one is enough):

- Existing code passes `server_url=...` (Python) or `dataPlaneUrl: ...` (TS) with a non-default host.
- `HH_DATA_PLANE_URL` (TS/CLI) or `HH_API_URL` (Python) is set in `.env`, deploy config, k8s manifest, or CI secrets.
- The user mentions a custom hostname or tenant name.
- Their HoneyHive UI lives at `app.<tenant>.us.honeyhive.ai` — the API host mirrors it (`api.<tenant>.us.honeyhive.ai`).

If you cannot confidently determine the host: **ask the user**. Do not default by inference.

## URL patterns

| Deployment | API host | UI host |
|---|---|---|
| Multi-tenant (default) | `https://api.dp1.us.honeyhive.ai` | `https://app.us.honeyhive.ai` |
| Dedicated | `https://api.<tenant>.us.honeyhive.ai` | `https://app.<tenant>.us.honeyhive.ai` |
| Self-host | Customer-defined (e.g. `https://honeyhive.<corp-domain>`) | Customer-defined |

## Common failure modes

- **401/403**: API key minted on a different deployment than the configured URL. Verify both came from the same workspace UI.
- **Spans silently dropping**: SDK defaulted to multi-tenant because `server_url=` (Python) or `dataPlaneUrl:` (TS) was not passed. Always pass explicitly.
- **TLS errors**: Self-host may use a custom CA — see [network-validation.md](network-validation.md) Step 3.
- **OTel collector silently exporting to default**: The OTLP exporter `endpoint:` doesn't auto-read the user's deployment URL. Set it to `${env:HH_DATA_PLANE_URL}/opentelemetry/v1/traces` (or `${env:HH_API_URL}/...` for Python users) explicitly. This failure is silent — only caught with verbose exporter logging.
