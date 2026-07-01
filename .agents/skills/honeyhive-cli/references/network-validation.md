# Network validation — curl fallback

This reference covers the **curl fallback** for when the HoneyHive CLI is not installed. The primary path is the [honeyhive-cli sanity check](../SKILL.md#sanity-check) which runs `honeyhive events search` directly.

> **Hard rule: do not proceed to runtime validation until reachability succeeds.** A wrong URL, wrong key, or blocked egress means every later step is rebuilding sand.

## Environment variables

- `HH_API_KEY` — project-scoped API key. **Must come from an env var, never a literal in code.**
- `HH_DATA_PLANE_URL` — deployment host. Multi-tenant default: `https://api.dp1.us.honeyhive.ai`; dedicated and self-host customers have their own. See [`dedicated-deployments.md`](dedicated-deployments.md).

If either is missing, direct the user to https://app.us.honeyhive.ai/settings/project/keys.

## Curl reachability check (fallback when CLI is not installed)

```bash
curl -sS -o /dev/null -w "HTTP %{http_code}\n" \
  -X POST \
  -H "Authorization: Bearer $HH_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"filters":[],"limit":1,"page":1}' \
  "${HH_DATA_PLANE_URL:-$HH_API_URL}/v1/events/search"
```

Interpretation:

| Result | Meaning | Action |
|---|---|---|
| `HTTP 200` | URL reachable, key valid | Proceed to Phase 0 runtime validation |
| `HTTP 401` | URL reachable, key invalid for this deployment | Stop — the key was minted for a different workspace, or it was revoked. Ask the user to confirm key + URL came from the same deployment UI |
| `HTTP 403` | URL reachable, key lacks scope | Stop — confirm the key is project-scoped, not personal-access |
| `HTTP 404` | Wrong URL path or wrong host | Stop — verify `HH_DATA_PLANE_URL` is correct (no trailing slash, correct subdomain) |
| `HTTP 000` / connection error | Egress blocked, DNS failure, or wrong host entirely | Stop — surface to the user; their network team may need to allow `:443` outbound to the host |
| `curl: (60)` SSL cert error | Self-host using a custom CA | See TLS cert chain section below |

Run the check exactly once. Do **not** retry on failure — surface the exact `curl` output and stop.

## TLS cert chain (self-host only)

If the user is on self-host and `curl` returns SSL errors, the runtime needs a custom CA bundle:

```bash
curl -v "${HH_DATA_PLANE_URL:-$HH_API_URL}/v1/events/search" 2>&1 | grep -E 'SSL|TLS|verify|certificate'
```

If "self signed certificate" or "unable to get local issuer certificate" appears, surface to the user. The fix depends on the deployment type:

**Self-hosted deployments:** The TLS certificate is issued for the customer's own domain. The customer's internal CA that signed that certificate must be trusted by the runtime where the SDK or collector runs. Ask the infrastructure or security team for that CA certificate bundle (often a `.pem` or `.crt` file). In corporate environments, check if the package manager or IT department distributes it (e.g., `/etc/ssl/certs/ca-certificates.crt` on Debian, or a custom path set by IT).

**Multi-tenant / dedicated deployments:** HoneyHive uses publicly trusted certificates (Let's Encrypt / AWS ACM), so no custom CA is needed under normal circumstances. However, corporate proxies that MITM outbound TLS connections will re-sign traffic with the proxy's own CA — in that case the proxy's CA certificate must be trusted by the runtime, just like a self-host CA would be.

To surface the exact hostname the network team needs to inspect or whitelist:

```bash
echo "${HH_DATA_PLANE_URL:-$HH_API_URL}" | sed 's|https://||'
```

Give the network team that hostname so they can verify the certificate chain, add firewall rules for `:443` egress, and — if a MITM proxy is in the path — confirm which CA the proxy uses to re-sign.

Configuration by runtime:
- For Python apps: `REQUESTS_CA_BUNDLE` / `SSL_CERT_FILE` env var pointing at the custom CA.
- For Node apps: `NODE_EXTRA_CA_CERTS` env var.
- For native OTel collectors: the exporter's `tls.ca_file` config.

Do not silently proceed with TLS verification disabled — surface as a finding and let the user wire the cert chain.

## Common failures (and how to read them)

- **401 with HH_DATA_PLANE_URL pointing at a dedicated tenant but key minted on multi-tenant** (or vice versa). Most common cause of "I copied the snippet from docs and it doesn't work" for dedicated customers. Confirm key + URL came from the same UI.
- **`curl` returns 200 but instrumentation later silently drops spans.** Likely a *different* env var setup at runtime than the one you tested with — check the user's process actually receives `HH_API_KEY` (e.g., docker-compose `env_file:`, k8s `envFrom:`, systemd `EnvironmentFile`). The validation curl ran in the user's shell; the app may run in a different env.
- **403 on a key that "used to work."** Either the key was rotated and the old one is revoked, or the user's API-key role was downgraded.
- **Connection error from inside a container/k8s pod but not from the user's laptop.** Egress policy blocks outbound `:443` to the HoneyHive host. Surface the URL + port to the user's network team; the skill can't fix this.

