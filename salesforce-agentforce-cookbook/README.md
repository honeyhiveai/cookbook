# Salesforce Agentforce × HoneyHive

Poll [Salesforce Agentforce](https://www.salesforce.com/agentforce/) [Session Trace OTel](https://developer.salesforce.com/docs/ai/agentforce/guide/otel-api.html) and forward each conversation as one HoneyHive session.

Agentforce does not push OpenTelemetry to an external endpoint. This cookbook is a stdlib-only poller you own and adapt. Salesforce setup and the HoneyHive session mapping live in the [Agentforce how-to](https://docs.honeyhive.ai/v2/integrations/salesforce-agentforce). Day-to-day skip lines, the state file, and recovery live in [OPERATING.md](./OPERATING.md).

One Agentforce conversation becomes one HoneyHive session with turn, model, and tool events.

## Prerequisites

| Requirement | Where to get it |
| --- | --- |
| Python 3.10+ | Standard library only. No `pip` install |
| Salesforce org with Agentforce and Data 360 | [Get Started with Agentforce](https://developer.salesforce.com/docs/ai/agentforce/guide/get-started.html) |
| Agentforce Session Tracing plus an External Client App | Follow [Enable tracing](https://docs.honeyhive.ai/v2/integrations/salesforce-agentforce#enable-tracing-in-salesforce) and [Create an External Client App](https://docs.honeyhive.ai/v2/integrations/salesforce-agentforce#create-an-external-client-app) |
| HoneyHive project API key | [Settings > Project > API Keys](https://app.us.honeyhive.ai/settings/project/keys) |
| A host with persistent storage | Needed for `.agentforce-exported.json`. systemd steps below assume Linux with root |

## Setup

```bash
git clone https://github.com/honeyhiveai/cookbook.git
cd cookbook/salesforce-agentforce-cookbook
cp poller.env.example poller.env
chmod 0600 poller.env
```

Fill in `poller.env` with an editor. Values must be unquoted and free of `$`, backticks, and spaces. Do not start a line with `export`, and do not indent keys. Leave `SALESFORCE_SESSION_ID`, `HONEYHIVE_SESSION_ID`, `HONEYHIVE_SESSION_NAME`, `MAX_PASSES`, and `DRY_RUN` out of this file. Pass those inline on a preview or pin.

```ini
HH_API_KEY=<your-api-key>
HH_API_URL=https://api.dp1.us.prod.honeyhive.ai
SALESFORCE_INSTANCE_URL=https://mydomain.my.salesforce.com
SALESFORCE_CLIENT_ID=<eca-consumer-key>
SALESFORCE_CLIENT_SECRET=<eca-consumer-secret>
```

`ls -l poller.env` should show `-rw-------`.

## Preview

Have at least one finished conversation with the activated agent first. Discovery only returns sessions Data 360 has written.

```bash
set -a
. ./poller.env
set +a
HONEYHIVE_SESSION_ID= HONEYHIVE_SESSION_NAME= SALESFORCE_SESSION_ID= DRY_RUN=1 MAX_PASSES=1 python3 poll_agentforce.py
```

Read a `Would export N span(s) for <salesforce-id> as <honeyhive-uuid> (ended <end-or-unset>)` line. `N` is spans, not turns: one Agentforce turn is several spans, so a three-turn chat can print `Would export 20 span(s)`.

- Pin the Salesforce ID after `for` on a `Would export` line you know has ended.
- A dry run does not read or write `.agentforce-exported.json`, and it skips the HoneyHive credential check.
- `ended unset` means the idle bound decided the conversation was finished. Any other value means Salesforce set `ssot__EndTimestamp__c`.

A sample looks like this:

```text
Discovered 20 session(s), 20 pending, 0 rejected
Pending: 01a02190-7c5e-74ee-b4a8-eff86af959e7, 7c1b9f22-3d41-4a88-9f0e-2b6c5d8e1a47, 5fd03ee0-c76d-4d57-9ed4-d43556ab8e73, ...
Skip 01a02190-7c5e-74ee-b4a8-eff86af959e7: no spans yet, Data 360 join is still catching up
Skip in-progress 7c1b9f22-3d41-4a88-9f0e-2b6c5d8e1a47
Would export 20 span(s) for 5fd03ee0-c76d-4d57-9ed4-d43556ab8e73 as 5fd03ee0-c76d-4d57-9ed4-d43556ab8e73 (ended unset)
```

Match skip lines in [OPERATING.md](./OPERATING.md#reject-and-pin-conditions).

## Pin one conversation

Pin from the same directory, with the same `poller.env`. Do not create the service account yet.

```bash
set -a
. ./poller.env
set +a
HONEYHIVE_SESSION_ID= HONEYHIVE_SESSION_NAME= DRY_RUN= SALESFORCE_SESSION_ID=<salesforce-id-from-a-would-export-line> MAX_PASSES=1 python3 poll_agentforce.py
```

On success this prints `Exported N span(s) for <salesforce-id> as <honeyhive-uuid>` and exits 0. Keep `MAX_PASSES=1`. A pin skips the completeness check, so it exports whatever Data 360 has joined at that moment.

If you are not certain the conversation has ended, mint a fresh HoneyHive UUID so the snapshot stays off the UUID discovery would use:

```bash
python3 -c "import uuid; print(uuid.uuid4())"
set -a
. ./poller.env
set +a
HONEYHIVE_SESSION_NAME= DRY_RUN= SALESFORCE_SESSION_ID=<salesforce-id-from-a-would-export-line> HONEYHIVE_SESSION_ID=<minted-uuid> MAX_PASSES=1 python3 poll_agentforce.py
```

Confirm the value after `as` is the literal you passed.

Then open [Traces > Sessions](https://app.us.honeyhive.ai/traces/sessions), find the row matching the UUID after `as`, and expect `N + 1` events for an `Exported N span(s)` line. HoneyHive adds the session row.

## Run the poller

Once that session lands in the right HoneyHive project with the turn count you expect, supervise the poller as a long-lived process. Do not run two pollers against one org.

Keep the host NTP-synced. Completeness and the 72-hour check both compare the host clock against Salesforce timestamps.

Downtime longer than Salesforce's 72-hour export window loses those conversations permanently.

### systemd

`./install.sh` creates `/srv/agentforce` and the `agentforce` user, then moves the poller modules, `poller.env`, and the state file there. Run it from this directory after the pin.

```bash
chmod +x install.sh
./install.sh
```

Write `/etc/systemd/system/agentforce-poller.service`:

```ini
[Unit]
Description=HoneyHive Agentforce session-trace poller
StartLimitIntervalSec=1800
StartLimitBurst=3

[Service]
User=agentforce
WorkingDirectory=/srv/agentforce
EnvironmentFile=/srv/agentforce/poller.env
Environment=PYTHONUNBUFFERED=1
ExecStart=/usr/bin/python3 /srv/agentforce/poll_agentforce.py
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
```

Confirm `poller.env` has no keep-outs, then start the unit:

```bash
sudo -u agentforce grep -nE '^[[:space:]]*(SALESFORCE_SESSION_ID|HONEYHIVE_SESSION_ID|HONEYHIVE_SESSION_NAME|MAX_PASSES|DRY_RUN)=' /srv/agentforce/poller.env
sudo systemctl daemon-reload
sudo systemctl enable --now agentforce-poller
```

From here on, every preview and pin runs from `/srv/agentforce` as `agentforce`:

```bash
sudo -u agentforce bash -c 'cd /srv/agentforce && set -a && . ./poller.env && set +a && HONEYHIVE_SESSION_ID= HONEYHIVE_SESSION_NAME= SALESFORCE_SESSION_ID= DRY_RUN=1 MAX_PASSES=1 python3 poll_agentforce.py'
```

`systemctl status` showing running is not evidence the poller is exporting. Read `journalctl -u agentforce-poller` and match lines in [OPERATING.md](./OPERATING.md).

### One-shot without systemd

```bash
set -a
. ./poller.env
set +a
HONEYHIVE_SESSION_ID= HONEYHIVE_SESSION_NAME= SALESFORCE_SESSION_ID= DRY_RUN= MAX_PASSES=1 python3 poll_agentforce.py
```

Leave `MAX_PASSES` unset (default `0`) to loop until you interrupt. For cron or a Kubernetes `CronJob`, keep `MAX_PASSES=1` and make overlap impossible (`flock`, or `concurrencyPolicy: Forbid`).

## Environment variables

| Variable | Required | Purpose |
| --- | --- | --- |
| `HH_API_KEY` | Yes, unless `DRY_RUN=1` | HoneyHive project API key |
| `HH_API_URL` | Yes, unless `DRY_RUN=1` | HoneyHive data plane base URL. Must start with `https://` or `http://`. Use `http://` only for an in-cluster self-hosted endpoint |
| `SALESFORCE_INSTANCE_URL` | Yes | My Domain login host (`https://<domain>.my.salesforce.com`) |
| `SALESFORCE_CLIENT_ID` | Yes | External Client App consumer key |
| `SALESFORCE_CLIENT_SECRET` | Yes | External Client App consumer secret |
| `SALESFORCE_API_VERSION` | No | REST API version (default `v66.0`). Keep the `v` prefix |
| `POLL_INTERVAL` | No | Seconds between passes (default `60`) |
| `MAX_PASSES` | No | Stop after this many loops (default `0`). Pass inline, not in `poller.env` |
| `DRY_RUN` | No | `1` / `true` / `yes` fetches without POSTing. Pass inline |
| `SALESFORCE_SESSION_ID` | No | Export this session only. Pass inline |
| `HONEYHIVE_SESSION_ID` | No | HoneyHive session UUID for a pin. Pass inline |
| `HONEYHIVE_SESSION_NAME` | No | Sessions-tab row name for a pin. Pass inline |
| `DISCOVERY_WINDOW_DAYS` | No | SOQL `LAST_N_DAYS` bound (default `4`) |
| `DISCOVERY_LIMIT` | No | Maximum sessions per discovery pass (default `20`) |
| `SESSION_IDLE_SECONDS` | No | Idle bound in seconds (default `120`) |
| `EXPORTED_FILE` | No | JSON file of exported and rejected IDs (default `.agentforce-exported.json`) |

Empty or whitespace-only values for the optional integers and `EXPORTED_FILE` use the default. A value that is not a whole number exits 1. `POLL_INTERVAL`, `DISCOVERY_LIMIT`, and `SESSION_IDLE_SECONDS` clamp values below `1` to `1`. `MAX_PASSES` and `DISCOVERY_WINDOW_DAYS` clamp a negative to `0`.

## What HoneyHive receives

The poller stamps `honeyhive.session_id`, `honeyhive.session_auto_create`, and `honeyhive.session_name` on the resource and every span, then POSTs to `{HH_API_URL}/opentelemetry/v1/traces`. It does not call `POST /v1/sessions`.

Session ID mapping:

```python
def honeyhive_session_id(sf_session_id: str) -> str:
    try:
        return str(uuid.UUID(sf_session_id))
    except ValueError:
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"agentforce:{sf_session_id}"))
```

Event types: `chain` for turns, `model` for LLM / router / classifier / guardrail steps, `tool` for state updates. Mapping details, leftover `input.value` / `output.value` buckets, and the sample tree are in the [how-to](https://docs.honeyhive.ai/v2/integrations/salesforce-agentforce#what-honeyhive-receives).

## Files

| File | Purpose |
| --- | --- |
| [`poll_agentforce.py`](./poll_agentforce.py) | Entrypoint: pin and discovery loops, POST OTLP |
| [`otel_map.py`](./otel_map.py) | HoneyHive session stamps and span mapping |
| [`policy.py`](./policy.py) | Idle bound, 72-hour window, skip/reject decisions |
| [`state.py`](./state.py) | Exported/rejected ledger |
| [`config.py`](./config.py) [`net.py`](./net.py) [`salesforce_api.py`](./salesforce_api.py) | Settings, HTTP, Salesforce calls |
| [`poller.env.example`](./poller.env.example) | Copy to `poller.env` |
| [`install.sh`](./install.sh) | Move the poller onto `/srv/agentforce` |
| [`repin.sh`](./repin.sh) | Bulk-pin after a wrong-project pass |
| [`OPERATING.md`](./OPERATING.md) | State file, skip lines, recovery |

## Links

- [How to integrate HoneyHive with Salesforce Agentforce](https://docs.honeyhive.ai/v2/integrations/salesforce-agentforce)
- [Export Agentforce Session Tracing Data (OTel API, beta)](https://developer.salesforce.com/docs/ai/agentforce/guide/otel-api.html)
- [HoneyHive tracing introduction](https://docs.honeyhive.ai/v2/tracing/introduction)
- [More HoneyHive cookbooks](../README.md)
