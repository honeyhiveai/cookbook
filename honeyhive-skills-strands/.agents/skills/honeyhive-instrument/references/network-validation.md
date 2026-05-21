# Network validation (Phase 0)

Before any setup or instrumentation work, confirm the user's environment can actually reach HoneyHive with the credentials they have. This is the cheapest check in the skill and catches the largest class of "spans never showed up" failures upfront.

> **Hard rule: do not proceed to Phase 1 setup until reachability succeeds.** A wrong URL, wrong key, or blocked egress means every later step is rebuilding sand.

## Step 1 — Source the credentials and URL from environment

Required env vars (or their setup-block equivalents — `.env`, k8s manifest, CI secrets, deploy config):

- `HH_API_KEY` — project-scoped API key. **Must come from an env var, never a literal in code.** If the user has a literal key anywhere in the existing source, flag it as a finding and refuse to copy it.
- `HH_API_URL` — the deployment host. Multi-tenant default is `https://api.dp1.us.honeyhive.ai`; dedicated and self-host customers have their own. See [`dedicated-deployments.md`](dedicated-deployments.md) for detection signals (existing `server_url` / `serverUrl` calls, tenant-prefixed hostnames, the user explicitly naming a deployment).

If `HH_API_KEY` is missing, the skill stops and asks the user. If `HH_API_URL` is missing **and** the user is on a dedicated/self-host deployment, the skill stops and asks. If `HH_API_URL` is missing and the user is genuinely on multi-tenant, fall back to the default — but confirm with the user, don't infer.

## Step 2 — Reachability check

If the `honeyhive` CLI is installed, run the bundled helper — it does the env-var checks and the authenticated probe in one call:

```bash
./preflight.sh
```

(See [`preflight.sh`](../preflight.sh) at the skill root. Set `HH_PROJECT` first if you want it to additionally confirm the project exists on the resolved deployment.)

If the CLI isn't available, run the equivalent `curl` directly:

```bash
curl -sS -o /dev/null -w "HTTP %{http_code}\n" \
  -H "Authorization: Bearer $HH_API_KEY" \
  "$HH_API_URL/projects"
```

Interpretation:

| Result | Meaning | Action |
|---|---|---|
| `HTTP 200` | URL reachable, key valid | Proceed to Phase 0 runtime validation |
| `HTTP 401` | URL reachable, key invalid for this deployment | Stop — the key was minted for a different workspace, or it was revoked. Ask the user to confirm key + URL came from the same deployment UI |
| `HTTP 403` | URL reachable, key lacks scope | Stop — confirm the key is project-scoped, not personal-access |
| `HTTP 404` | Wrong URL path or wrong host | Stop — verify `HH_API_URL` is correct (no trailing slash, correct subdomain) |
| `HTTP 000` / connection error | Egress blocked, DNS failure, or wrong host entirely | Stop — surface to the user; their network team may need to allow `:443` outbound to the host |
| `curl: (60)` SSL cert error | Self-host using a custom CA | See Step 3 |

Run the check exactly once. Do **not** retry on failure — surface the exact `curl` output and stop.

## Step 3 — TLS cert chain (self-host only)

If the user is on self-host and `curl` returns SSL errors, the runtime needs a custom CA bundle:

```bash
curl -v "$HH_API_URL/projects" 2>&1 | grep -E 'SSL|TLS|verify|certificate'
```

If "self signed certificate" or "unable to get local issuer certificate" appears, surface to the user:
- For Python apps: `REQUESTS_CA_BUNDLE` / `SSL_CERT_FILE` env var pointing at the custom CA.
- For Node apps: `NODE_EXTRA_CA_CERTS` env var.
- For native OTel collectors: the exporter's `tls.ca_file` config.

Do not silently proceed with TLS verification disabled — surface as a finding and let the user wire the cert chain.

## Common failures (and how to read them)

- **401 with HH_API_URL pointing at a dedicated tenant but key minted on multi-tenant** (or vice versa). Most common cause of "I copied the snippet from docs and it doesn't work" for dedicated customers. Confirm key + URL came from the same UI.
- **`curl` returns 200 but instrumentation later silently drops spans.** Likely a *different* env var setup at runtime than the one you tested with — check the user's process actually receives `HH_API_KEY` (e.g., docker-compose `env_file:`, k8s `envFrom:`, systemd `EnvironmentFile`). The validation curl ran in the user's shell; the app may run in a different env.
- **403 on a key that "used to work."** Either the key was rotated and the old one is revoked, or the user's API-key role was downgraded.
- **Connection error from inside a container/k8s pod but not from the user's laptop.** Egress policy blocks outbound `:443` to the HoneyHive host. Surface the URL + port to the user's network team; the skill can't fix this.

## Output to Phase 0 runtime-validation

If reachability succeeds, record the validated values for the rest of the skill to use:

```
HH_API_KEY = <from env, validated>
HH_API_URL = <from env or default, validated>
deployment_type = multi-tenant | dedicated | self-host
```

Runtime validation (next step) and Phase 1 setup pick these up rather than re-detecting them.
