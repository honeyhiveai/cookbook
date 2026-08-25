# Salesforce Agentforce × HoneyHive

Poll [Salesforce Agentforce](https://www.salesforce.com/agentforce/) [Session Trace OTel](https://developer.salesforce.com/docs/ai/agentforce/guide/otel-api.html) and forward each conversation as one HoneyHive session.

Agentforce does not push OpenTelemetry to an external endpoint. This cookbook is a beta reference poller (Python standard library only). Copy it and run it wherever you want.

One Agentforce conversation becomes one HoneyHive session. Session Trace exports the full Agentforce graph, so one user turn is several events (the turn itself, a state update, a guardrail, a topic router, the topic LLM call, and an instruction check). The poller rewrites Salesforce kvlists and `agent.messages.*` keys into GenAI / OpenInference JSON strings so HoneyHive Input/Output panels fill in.

## Prerequisites

| Requirement | Where to get it |
| --- | --- |
| Python 3.10+ | Standard library only. No `pip` install |
| Salesforce org with Agentforce and Data 360 | [Get Started with Agentforce](https://developer.salesforce.com/docs/ai/agentforce/guide/get-started.html) |
| Agentforce Session Tracing plus an External Client App | Follow [Salesforce setup](#salesforce-setup) |
| HoneyHive project API key | [Settings > Project > API Keys](https://app.us.honeyhive.ai/settings/project/keys) |

## Setup

```bash
git clone https://github.com/honeyhiveai/cookbook.git
cd cookbook/salesforce-agentforce-cookbook
cp poller.env.example poller.env
chmod 0600 poller.env
```

Fill in `poller.env`:

```ini
HH_API_KEY=<your-api-key>
HH_API_URL=https://api.dp1.us.prod.honeyhive.ai
SALESFORCE_INSTANCE_URL=https://mydomain.my.salesforce.com
SALESFORCE_CLIENT_ID=<eca-consumer-key>
SALESFORCE_CLIENT_SECRET=<eca-consumer-secret>
```

## Salesforce setup

Do this in the Salesforce org before you run the poller. Salesforce's [Session Trace OTel guide](https://developer.salesforce.com/docs/ai/agentforce/guide/otel-api.html) has the current steps.

1. Turn on **Data 360**. Confirm a dataspace under **Setup > Einstein Audit, Analytics, and Monitoring Setup**.
2. Turn on **Agentforce Session Tracing** and **Audit and Feedback**. Refresh `AiAgentSession`, `AiAgentInteraction`, `AiAgentInteractionMessage`, and `AiAgentInteractionStep` in **Data Cloud > Data Streams**.
3. **Activate** (publish) the agent. Draft-only preview sessions often do not show up.
4. Create an [External Client App](https://help.salesforce.com/s/articleView?id=sf.external_client_apps.htm) with the `api` scope and Client Credentials Flow. **Run As** needs Data Cloud access and Einstein Audit read access. Copy the consumer key, secret, and My Domain host (`https://<domain>.my.salesforce.com`).

## Preview

Have at least one finished conversation with the activated agent first.

```bash
set -a
. ./poller.env
set +a
DRY_RUN=1 python3 poll_agentforce.py
```

Look for `Would export N span(s) for <salesforce-id> as <honeyhive-uuid>`. `N` is spans, not turns: one Agentforce turn is several spans.

- `Skip <id>: in-progress` means the conversation is still going.
- `Skip <id>: no spans yet` means Data 360 has the session row but OTel spans have not joined yet.

## Export

Same directory, same `poller.env`. This run POSTs to HoneyHive.

```bash
set -a
. ./poller.env
set +a
python3 poll_agentforce.py
```

To export one session only:

```bash
set -a
. ./poller.env
set +a
SALESFORCE_SESSION_ID=<salesforce-id-from-a-would-export-line> python3 poll_agentforce.py
```

On success the script prints `Exported N span(s) for <salesforce-id> as <honeyhive-uuid>`. Open [Traces > Sessions](https://app.us.honeyhive.ai/traces/sessions) and match the **HoneyHive UUID** (it is derived from the Salesforce id, not equal to it). A first export of `N` spans shows `N + 1` events because HoneyHive adds the session row. Use **All time** if the conversation is older than the default range.

Exported IDs are stored in `.agentforce-exported.json` so a later run does not POST the same session again. Pinning `SALESFORCE_SESSION_ID` still POSTs. Re-exporting the same Salesforce session appends spans onto the same HoneyHive session. Set `HONEYHIVE_SESSION_ID` to a new UUID if you want a fresh tree.

## Run it again

The default is one pass (`MAX_PASSES=1`). To keep polling until you interrupt:

```bash
set -a
. ./poller.env
set +a
MAX_PASSES=0 python3 poll_agentforce.py
```

Deploy that however you want: a terminal, cron, or a container. This is a beta reference, not a packaged service.

Salesforce documents a 72-hour export window. Sessions older than that are gone.

## Environment variables

| Variable | Required | Purpose |
| --- | --- | --- |
| `HH_API_KEY` | Yes, unless `DRY_RUN=1` | HoneyHive project API key |
| `HH_API_URL` | Yes, unless `DRY_RUN=1` | HoneyHive data plane base URL |
| `SALESFORCE_INSTANCE_URL` | Yes | My Domain login host (`https://<domain>.my.salesforce.com`) |
| `SALESFORCE_CLIENT_ID` | Yes | External Client App consumer key |
| `SALESFORCE_CLIENT_SECRET` | Yes | External Client App consumer secret |
| `DRY_RUN` | No | `1` fetches without POSTing |
| `SALESFORCE_SESSION_ID` | No | Export this session only |
| `HONEYHIVE_SESSION_ID` | No | Override the derived HoneyHive session UUID. Must be a UUID |
| `MAX_PASSES` | No | Stop after this many loops (default `1`). `0` loops until interrupted |
| `POLL_INTERVAL` | No | Seconds between loops when `MAX_PASSES=0` (default `60`) |

## Files

| File | Purpose |
| --- | --- |
| [`poll_agentforce.py`](./poll_agentforce.py) | Discover, fetch, map, POST |
| [`otel_map.py`](./otel_map.py) | Session grouping, span kind, and I/O rewrite onto public GenAI / OpenInference JSON strings |
| [`poller.env.example`](./poller.env.example) | Copy to `poller.env` |

## Links

- [How to integrate HoneyHive with Salesforce Agentforce](https://docs.honeyhive.ai/v2/integrations/salesforce-agentforce)
- [Export Agentforce Session Tracing Data (OTel API, beta)](https://developer.salesforce.com/docs/ai/agentforce/guide/otel-api.html)
- [HoneyHive tracing introduction](https://docs.honeyhive.ai/v2/tracing/introduction)
- [More HoneyHive cookbooks](../README.md)
