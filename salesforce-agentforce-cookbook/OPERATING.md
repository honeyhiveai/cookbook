# Operating the Agentforce poller

Skip lines, the state file, discovery window, and recovery. Preview, pin, and start the unit from [README.md](./README.md).

Recovery commands use the systemd layout from the README: `sudo -u agentforce bash -c 'cd /srv/agentforce && ...'`.

| Variable | Default |
| --- | --- |
| `EXPORTED_FILE` | `.agentforce-exported.json` |
| `DRY_RUN` | unset (POST) |
| `DISCOVERY_WINDOW_DAYS` | `4` |
| `DISCOVERY_LIMIT` | `20` |
| `SESSION_IDLE_SECONDS` | `120` |
| `POLL_INTERVAL` | `60` |
| `MAX_PASSES` | `0` |
| `SALESFORCE_API_VERSION` | `v66.0` |

## State file

The poller writes exported and rejected session IDs to `.agentforce-exported.json` (override with `EXPORTED_FILE`). Run it from a stable working directory.

Sending the same session twice creates duplicate traces. The exported-ID list is the guard.

- Two pollers against the same org double-POST immediately, even on separate state files.
- A HoneyHive POST that times out after HoneyHive accepted the payload is retried next pass and duplicates that session.
- If you lose the file, a restart re-exports every completed session still inside the discovery window.

On startup the poller reads the file and writes it back once, so an unreadable or unwritable path exits before the first HoneyHive POST. `DRY_RUN=1` skips the file.

A leftover `{EXPORTED_FILE}.tmp` that parses as JSON stops every later start. Stop the poller first, then:

- If it is a JSON object with `exported` and `rejected` lists, `sudo -u agentforce mv` it onto `{EXPORTED_FILE}`.
- Anything else: delete it rather than moving it.

Then `systemctl reset-failed agentforce-poller` before starting again.

- `exported` holds only sessions that POSTed to HoneyHive.
- `rejected` holds IDs the poller will not retry. See [Reject and pin conditions](#reject-and-pin-conditions).
- `reject_reasons` maps those IDs to slug strings.

To retry an ID in `rejected`:

1. Stop the poller.
2. Remove the ID from `rejected` with `sudoedit` on `{EXPORTED_FILE}`. Keep `exported` and `rejected` as lists.
3. Restart.

An edit made while the poller runs is reverted on the next write.

```json
{
  "exported": ["5fd03ee0-c76d-4d57-9ed4-d43556ab8e73"],
  "rejected": ["7c1b9f22-3d41-4a88-9f0e-2b6c5d8e1a47"],
  "reject_reasons": {
    "7c1b9f22-3d41-4a88-9f0e-2b6c5d8e1a47": "hh_400"
  }
}
```

### 72-hour removal rule

Removing an ID only re-exports while the conversation is still inside Salesforce's 72-hour export window and discovery still returns it.

- **Inside 72 hours, still in newest-`DISCOVERY_LIMIT` and `DISCOVERY_WINDOW_DAYS`:** remove the ID and restart.
- **Inside 72 hours, scrolled out of either:** pin instead.
- **Past 72 hours:** do not remove the ID. Salesforce no longer serves the payload.

A host clock running ahead of Salesforce can mark a conversation that is still inside 72 hours as expired. NTP-sync and pin if the printed `started` timestamp is still inside the window.

## Reading the output

Each pass prints how many discovered sessions are pending and how many are rejected. A pin always prints `Discovered 1 session(s)`.

```text
Discovered 1 session(s), 1 pending, 0 rejected
Pending: 5fd03ee0-c76d-4d57-9ed4-d43556ab8e73
Exported 20 span(s) for 5fd03ee0-c76d-4d57-9ed4-d43556ab8e73 as 5fd03ee0-c76d-4d57-9ed4-d43556ab8e73
```

`Exported N span(s)` is the number of spans HoneyHive answered with `200`. On a first export of that session ID, expect `N + 1` events on the Sessions tab, because HoneyHive adds the session row.

Any HTTP error body, from Salesforce or from HoneyHive, prints on its own line.

| Line | Prints |
| --- | --- |
| `Hit DISCOVERY_LIMIT=...` | Once per process |
| `Could not read ssot__StartTimestamp__c` | Once per session ID per process |
| `Would export N span(s) for <id> as <uuid> (ended ...)` | Dry run only |
| `Skip in-progress <id>` | Every pass until idle, EndTimestamp is set, or the session leaves discovery |
| `Skip <id>: no spans yet, Data 360 join is still catching up` | Every pass until spans arrive or the start passes 72 hours |
| `Skip <id>: empty spans` | Discovery on a real pass, once |

`ended unset` means idle treated it as finished. Any other value is the `ssot__EndTimestamp__c` string Salesforce returned. `ended unknown` is a pin.

## Setting the idle bound

Raise `SESSION_IDLE_SECONDS` above how long a person takes to answer after the agent's last reply, plus the Data 360 join lag. The default `120` is tuned for a quiet demo org.

A pin skips the idle check. Any non-blank `ssot__EndTimestamp__c` also skips it. Values below `1` become `1`, but `1` treats almost every live conversation as finished.

## Tuning the discovery window

| `DISCOVERY_WINDOW_DAYS` | Coverage | Dead band |
| --- | --- | --- |
| `3` | 72 to 96 hours | Up to 24 hours |
| `4` (default) | 96 to 120 hours | 24 to 48 hours |
| `1` or `2` | Under 72 hours | None, but drops sessions Salesforce can still export |
| `0` | No time filter | Unbounded |

Recording an ID does not free its slot. Size `DISCOVERY_LIMIT` against the conversations your org starts in the whole window, not against the ones still pending.

Each pass returns only the newest `DISCOVERY_LIMIT` sessions (default 20). Raise `DISCOVERY_LIMIT` with `SESSION_IDLE_SECONDS`: a long idle wait plus a small newest-N can drop a conversation before it is eligible.

Raise `POLL_INTERVAL` on a Developer Edition org or after a quota `403`.

## Pinning a session

After install, pin from `/srv/agentforce` as `agentforce`:

```bash
sudo -u agentforce bash -c 'cd /srv/agentforce && set -a && . ./poller.env && set +a && HONEYHIVE_SESSION_ID= HONEYHIVE_SESSION_NAME= DRY_RUN= SALESFORCE_SESSION_ID=<id> MAX_PASSES=1 python3 poll_agentforce.py'
```

Use a pin when discovery will not see the ID again: rejected, or scrolled out of newest-N. Keep `MAX_PASSES=1`.

A conversation still printing `Skip in-progress` is not finished. If you pin one anyway, set a custom `HONEYHIVE_SESSION_ID` so the snapshot stays off the UUID discovery would use. The Salesforce ID still goes into `exported`, so you have to remove it from the file or pin again once the conversation ends.

Stop any poller already running against this org before you pin or edit.

## Recovering a truncated export

| Recovery | Lands on | Result |
| --- | --- | --- |
| Remove the ID from `exported`, let discovery re-export | The same session UUID | Clean only if the first export used a custom UUID. Otherwise snapshot turns are duplicated |
| Pin again with a fresh `HONEYHIVE_SESSION_ID` | The UUID you pass | Clean. The snapshot stays behind on a second row you can ignore |

If `ssot__EndTimestamp__c` is set, removing the ID cannot help. Pin onto a fresh UUID.

Confirm the span count before you re-pin. A pin skips the completeness check every time.

```bash
sudo -u agentforce bash -c 'cd /srv/agentforce && set -a && . ./poller.env && set +a && HONEYHIVE_SESSION_ID= HONEYHIVE_SESSION_NAME= DRY_RUN=1 SALESFORCE_SESSION_ID=<id> MAX_PASSES=1 python3 poll_agentforce.py'
```

Both routes stop at Salesforce's 72-hour export window.

## Reject and pin conditions

Printed slugs:

- `expired`: Salesforce `400`/`404` on a session fetch, start past 72 hours; empty spans past 72 hours
- `missing_start`: Null start, fetch miss (`DISCOVERY_WINDOW_DAYS=0`, small orgs only)
- `empty_missing_start`: Null start, empty `200` with EndTimestamp set
- `unreadable`: Unreadable OTLP payload
- `mapping`: Mapping error
- `hh_400`: HoneyHive `400`

A bounded pin (`MAX_PASSES` set) exits 1 when the last pass did not export. A bounded discovery run exits 1 only when the last pass could not authenticate or discover sessions.

| Condition | Slug | Pinned | Discovery |
| --- | --- | --- | --- |
| Salesforce `400`/`404` on token or discovery | none | Exits 1 | Exits 1 |
| Salesforce `400`/`404` on a session fetch, start past 72 hours | `expired` | Exits 1 | Records |
| Salesforce `400`/`404` on a session fetch, start inside 72 hours | none | Exits 1 | Not recorded. Reprints until the start passes 72 hours |
| Null start (`DISCOVERY_WINDOW_DAYS=0`) | `missing_start` / `empty_missing_start` | Exits 1 or polls | Records fetch miss and empty `200` with EndTimestamp |
| Salesforce `401` | none | Retries | Retries |
| Salesforce `403` quota | none | Retries | Retries |
| Salesforce `INSUFFICIENT_ACCESS` / `API_DISABLED_FOR_ORG` | none | Exits 1 | Exits 1. Discovery can succeed and every fetch still fail: Data Cloud and Einstein Audit are separate permissions |
| HoneyHive `401`/`403`/`404` | none | Exits 1 | Exits 1. `401` is a bad key. `404` is a bad `HH_API_URL` |
| HoneyHive `400` | `hh_400` | Exits 1 | Records. The payload was rejected |
| Mapping error | `mapping` | Exits 1 | Records |
| Unreadable OTLP payload | `unreadable` | Exits 1 | Records |
| Newest span inside `SESSION_IDLE_SECONDS` | none | Snapshot export | Not recorded; retried |
| Empty spans, start inside 72 hours | none | Polls | Not recorded |
| Empty spans, start past 72 hours | `expired` | Exits 1 or polls | Records |
| Network error or other HTTP status | none | Retries. A timeout after HoneyHive accepted the payload duplicates | Retries. Same duplication risk |
| Unreadable or unwritable state file | none | Exits 1 | Exits 1 |

The unknown-session exit is `Unknown session ID, or the session is past the 72-hour window, or the org does not support <SALESFORCE_API_VERSION>`. `GET {SALESFORCE_INSTANCE_URL}/services/data/` lists the versions the org does support.

## When discovery returns nothing

`Discovered 0 session(s), 0 pending, 0 rejected` as the only line:

- No conversation exists yet. Have at least one conversation with the activated agent, let it finish, then re-run the preview.
- The conversation is outside `DISCOVERY_WINDOW_DAYS`.
- Data 360 has no session rows yet. Wait, or check **Data Cloud > Data Streams**.

## Recovering a half-finished install

[`install.sh`](./install.sh) copies the poller, `poller.env`, and the state file into `/srv/agentforce`, then deletes the relative leftovers in the current directory.

- If you pinned and the state file is missing on the host, copy it after the script finishes. Without it the first supervised pass re-exports that conversation.
- A failed `install` leaves the files in the current directory. Fix the cause and re-run.

## Empty or 404 session fetches

Confirm Agentforce Session Tracing is on and the OTel response has spans. Salesforce documents a 72-hour window. If discovery lists IDs and every fetch returns `404`, refresh `AiAgentSession`, `AiAgentInteraction`, `AiAgentInteractionMessage`, and `AiAgentInteractionStep` in **Data Cloud > Data Streams**. A `404` on every request, including discovery, can also mean the org does not support `SALESFORCE_API_VERSION` (default `v66.0`).
