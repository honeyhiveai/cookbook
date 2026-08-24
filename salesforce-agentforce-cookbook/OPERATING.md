# Operating the Agentforce poller

Day-to-day reference for [`poll_agentforce.py`](./poll_agentforce.py). Preview, pin, and start the unit from [README.md](./README.md). Come here to read the state file, decode a skip line, size the discovery window, or recover a pin, a wrong-project pass, or a half-finished install.

Recovery commands use the systemd layout from the README: `sudo -u agentforce bash -c 'cd /srv/agentforce && ...'`. A container is an adaptation of that layout.

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

## Running these on a container

`sudo -u agentforce bash -c '...'` substitutes `docker exec -u agentforce -w /srv/agentforce <container> bash -c '...'` or `kubectl exec <pod> -- bash -c 'cd /srv/agentforce && ...'`.

- `docker exec` without `bash -c` treats the quoted compound command as a program name.
- Here-docs that rebuild `ids.txt` read stdin, so those need `docker exec -i` or `kubectl exec -i`.
- `kubectl exec` cannot select a user, so the image `USER` has to be the service account.
- After `docker cp`, `chown` as root before `chmod`. After `kubectl cp`, only the mode needs fixing (`chmod 0755` on `repin.sh`). `kubectl cp` also needs `tar` in the image.
- With `docker run --env-file` there is no `poller.env` inside the container. Drop the `set -a && . ./poller.env && set +a` prefix; the values are already in the environment.
- `repin.sh` needs `bash` plus `awk`, `tr`, `cmp`, `tee`, `date`, `python3`, and (for `kubectl cp`) `tar`. Do not run it under `sh`.

## State file

The poller writes exported and rejected session IDs to `.agentforce-exported.json` (override with `EXPORTED_FILE`). Run it from a stable working directory. In a container, mount it on a volume.

This poller does not set `honeyhive_event_id`, so a re-POST writes a second span tree. The exported-ID list is the primary guard.

- Two pollers against the same org double-POST immediately, even on separate state files. A shared file is last-write-wins.
- A HoneyHive POST that times out after HoneyHive accepted the payload is retried next pass and duplicates that session.
- If you lose the file, a restart re-exports every completed session still inside the discovery window.

On startup the poller reads the file and writes it back once, so an unreadable, unexpected-shape, or unwritable path exits before the first HoneyHive POST. `DRY_RUN=1` skips the file.

A leftover `{EXPORTED_FILE}.tmp` that parses as JSON stops every later start. Stop whatever writes the file first, then:

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

The expired check compares the poller host's `time.time()` to `ssot__StartTimestamp__c`. A host running ahead can mark a conversation that is still inside 72 hours as expired. NTP-sync and pin if the printed `started` timestamp is still inside the window.

## Reading the output

Each pass prints how many discovered sessions are pending and how many are rejected. Both counts are taken before the per-session loop runs. A pin always prints `Discovered 1 session(s)` without running the discovery query.

```text
Discovered 1 session(s), 1 pending, 0 rejected
Pending: 5fd03ee0-c76d-4d57-9ed4-d43556ab8e73
Exported 20 span(s) for 5fd03ee0-c76d-4d57-9ed4-d43556ab8e73 as 5fd03ee0-c76d-4d57-9ed4-d43556ab8e73
```

`Exported N span(s)` is the number of spans HoneyHive answered with `200`. On a first export of that session ID, expect `N + 1` events on the Sessions tab, because HoneyHive adds the session row. Re-exporting a session ID that already has a row adds `N` events and no row.

Any HTTP error body, from Salesforce or from HoneyHive, prints on its own line with no prefix.

| Line | Prints |
| --- | --- |
| `Hit DISCOVERY_LIMIT=...` | Once per process |
| `Could not read ssot__StartTimestamp__c` | Once per session ID per process |
| `Would export N span(s) for <id> as <uuid> (ended ...)` | Dry run only, once per session ID per process |
| `Skip in-progress <id>` | Every pass until idle, EndTimestamp is set, or the session leaves discovery |
| `Skip <id>: no spans yet, Data 360 join is still catching up` | Every pass until spans arrive or the start passes 72 hours |
| `Skip <id>: empty spans` | Discovery on a real pass, once |

`ended unset` means idle treated it as finished. Any other value is the `ssot__EndTimestamp__c` string Salesforce returned. `ended unknown` is a pin.

## Setting the idle bound

Raise `SESSION_IDLE_SECONDS` above how long a person takes to answer after the agent's last reply, plus the Data 360 join lag. The default `120` is tuned for a quiet demo org.

Three things bypass the bound:

- A pin. It skips the completeness check.
- Any non-blank `ssot__EndTimestamp__c` string. The value is never parsed.
- A host clock ahead of Salesforce by more than `SESSION_IDLE_SECONDS`.

Values below `1` become `1`, but `1` treats almost every live conversation as finished.

## Tuning the discovery window

`LAST_N_DAYS` is a calendar-day literal.

| `DISCOVERY_WINDOW_DAYS` | Coverage | Dead band |
| --- | --- | --- |
| `3` | 72 to 96 hours | Up to 24 hours |
| `4` (default) | 96 to 120 hours | 24 to 48 hours |
| `1` or `2` | Under 72 hours | None, but drops sessions Salesforce can still export |
| `0` | No time filter | Unbounded |

### Sizing DISCOVERY_LIMIT

Recording an ID does not free its slot. Size `DISCOVERY_LIMIT` against the conversations your org starts in the whole window (96 to 120 hours at the default `4`), not against the ones still pending.

Each pass still returns only the newest `DISCOVERY_LIMIT` sessions (default 20). Raise `DISCOVERY_LIMIT` with `SESSION_IDLE_SECONDS`: a long idle wait plus a small newest-N can drop a conversation out of the result before it is eligible, with no entry in either list.

Each discovery pass costs one token request, one SOQL query, and one OTel fetch per pending session, plus one HoneyHive POST per exported session. Raise `POLL_INTERVAL` on a Developer Edition org or after a quota `403`.

## Pinning a session

After install, every bare `python3 poll_agentforce.py` means this wrapper:

```bash
sudo -u agentforce bash -c 'cd /srv/agentforce && set -a && . ./poller.env && set +a && HONEYHIVE_SESSION_ID= HONEYHIVE_SESSION_NAME= DRY_RUN= SALESFORCE_SESSION_ID=<id> MAX_PASSES=1 python3 poll_agentforce.py'
```

Use a pin when discovery will not see the ID again: rejected, posted to the wrong project, or scrolled out of newest-N. Keep `MAX_PASSES=1`. At the default `MAX_PASSES=0` a pin that does not export never exits.

A conversation still printing `Skip in-progress` is not finished. If you pin one anyway, set a custom `HONEYHIVE_SESSION_ID` so the snapshot stays off the UUID discovery would use. The Salesforce ID still goes into `exported`, so you have to remove it from the file or pin again once the conversation ends.

Stop any poller already running against this org before you pin or edit.

## Recovering a truncated export

| Recovery | Lands on | Result |
| --- | --- | --- |
| Remove the ID from `exported`, let discovery re-export | The derived UUID, always | Clean only if the first export was a pin on a custom UUID. Otherwise snapshot turns are duplicated and timing stays frozen |
| Pin again with a fresh `HONEYHIVE_SESSION_ID` | The UUID you pass | Clean. The snapshot stays behind on a second row you can ignore |
| Pin again on a UUID that already has a row | That row | Duplicated turns, frozen timing |

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

A bounded pin (`MAX_PASSES` set) exits 1 when the last pass did not export. A bounded discovery run exits 1 only when the last pass could not authenticate or discover sessions, or on a fatal condition.

| Condition | Slug | Pinned | Discovery |
| --- | --- | --- | --- |
| Salesforce `400`/`404` on token or discovery | none | Exits 1 | Exits 1 |
| Salesforce `400`/`404` on a session fetch, start past 72 hours | `expired` | Exits 1 | Records |
| Salesforce `400`/`404` on a session fetch, start inside 72 hours | none | Exits 1 | Not recorded. Reprints until the start passes 72 hours |
| Null start (`DISCOVERY_WINDOW_DAYS=0`) | `missing_start` / `empty_missing_start` | Exits 1 or polls | Records fetch miss and empty `200` with EndTimestamp |
| Salesforce `401` | none | Retries | Retries |
| Salesforce `403` quota | none | Retries, no backoff | Retries, no backoff |
| Salesforce `INSUFFICIENT_ACCESS` / `API_DISABLED_FOR_ORG` | none | Exits 1 | Exits 1. Discovery can succeed and every fetch still fail: Data Cloud and Einstein Audit are separate permissions |
| HoneyHive `401`/`403`/`404` | none | Exits 1 | Exits 1. `401` is a bad key. `404` is a bad `HH_API_URL` |
| HoneyHive `400` | `hh_400` | Exits 1 | Records. Decode or size failure (the 50 MB body cap is `400`, not `413`) |
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
- Data 360 has no `ssot__AiAgentSession__dlm` rows yet. Wait, or check **Data Cloud > Data Streams**.
- The query answered `200` with a JSON object that has no `records` key.

## Recovering a half-finished install

[`install.sh`](./install.sh) copies the poller modules, `poller.env`, and the state file into `/srv/agentforce`, then deletes the relative leftovers in the current directory.

- If you pinned and the state file is missing on the host, copy it after the script finishes and `sudo install -o agentforce -m 0644` it to the dest. Without it the first supervised pass re-exports that conversation.
- A failed `install` leaves the files in the current directory. Fix the cause and re-run.

```bash
{ [ ! -e poll_agentforce.py ] && [ ! -e poller.env ]; } \
  && echo "clean: no leftover script or env file here" \
  || echo "leftovers: poller modules or poller.env is still in this directory"
env | grep -q '^HH_API_KEY=' \
  && echo "sourced exports still set in this shell; unset HH_API_KEY HH_API_URL SALESFORCE_INSTANCE_URL SALESFORCE_CLIENT_ID SALESFORCE_CLIENT_SECRET EXPORTED_FILE" \
  || echo "clean: HH_API_KEY is not exported in this shell"
```

## Recovering a wrong-project pass

A pass that POSTed to the wrong project still recorded every session as exported, so `0 pending` with no `Skip` line means the poller considers them done.

1. Stop the poller.
2. Fix `HH_API_KEY`.
3. Check whether the wrong project is in the same HoneyHive org as the right one.

The state file is a candidate list, not the membership and not the order. It over-reports (sessions that already landed in the right project) and under-reports (accepted POSTs that timed out). Walk `ssot__AiAgentSession__dlm` newest-first, derive each HoneyHive UUID, and keep IDs whose derived UUID has a row in the **wrong** project.

- **Different orgs (`SAME_ORG=0`):** pin without `HONEYHIVE_SESSION_ID`. The derived UUID does not collide across orgs.
- **Same org (`SAME_ORG=1`):** pin each ID with a fresh `HONEYHIVE_SESSION_ID`. Do not remove those IDs from `exported` and restart: discovery would land on the derived UUID and hit the wrong project's cached row.

Mint the UUID as its own step so you can check it. A failed mint is silent: the poller treats an empty `HONEYHIVE_SESSION_ID` as unset and falls back to the derived UUID.

```bash
python3 -c "import uuid; print(uuid.uuid4())"
sudo -u agentforce bash -c 'cd /srv/agentforce && set -a && . ./poller.env && set +a && HONEYHIVE_SESSION_NAME= DRY_RUN= SALESFORCE_SESSION_ID=<id> HONEYHIVE_SESSION_ID=<minted-uuid> MAX_PASSES=1 python3 poll_agentforce.py'
```

### Pin many conversations

Write `ids.txt` (one Salesforce session ID per line, newest first), then:

```bash
sudo install -o agentforce -m 0644 ids.txt /srv/agentforce/ids.txt
sudo install -o agentforce -m 0755 repin.sh /srv/agentforce/repin.sh
sudo -u agentforce bash -c 'cd /srv/agentforce && set -a && . ./poller.env && set +a && SAME_ORG=1 ./repin.sh'
```

Use `SAME_ORG=0` when the leak was to a different org.

[`repin.sh`](./repin.sh) stops after three consecutive failures or ten total. It writes `ids.remaining.txt`, `ids.done.txt`, `ids.dedup.txt`, and `agentforce-repin.log`.

| State | What happened | Do this before re-running |
| --- | --- | --- |
| `ids.remaining.txt` non-empty | The loop hit a bound | Rebuild `ids.txt` from `ids.dedup.txt` minus IDs that have an `Exported` line in `agentforce-repin.log` |
| `ids.done.txt` shorter than `ids.dedup.txt` | Interrupt or crash | Same rebuild, subtracting `Exported` lines, not the ledger |
| `ids.done.txt` the same line count as `ids.dedup.txt` | The walk finished | `rm ids.done.txt ids.txt` |
| `ids.txt` absent | The campaign is done | Nothing unless the attempt printed `Would export` and no `Exported` line (leftover `DRY_RUN=1`) |

After an interrupt, rebuild with this here-doc:

```bash
sudo -u agentforce bash -s <<'EOF'
cd /srv/agentforce || exit 1
[ -s ids.done.txt ] || { echo "ids.done.txt is missing or empty"; exit 1; }
[ -s ids.dedup.txt ] || { echo "ids.dedup.txt is missing or empty"; exit 1; }
if [ "$(wc -l < ids.done.txt)" -eq "$(wc -l < ids.dedup.txt)" ]; then
  echo "The walk finished. Run 'rm ids.done.txt ids.txt' instead"
  exit 1
fi
[ -s agentforce-repin.log ] || { echo "agentforce-repin.log is missing or empty"; exit 1; }
awk '/^Exported [0-9]+ span\(s\) for /{d[$5]} END{for (i in d) print i}' \
  agentforce-repin.log > ids.exported.txt || exit 1
awk 'FILENAME==ARGV[1]{d[$0];next} !($0 in d)' ids.exported.txt ids.dedup.txt > ids.next.txt || exit 1
[ -s ids.next.txt ] || { rm -f ids.next.txt ids.exported.txt; echo "Every ID already has an Exported line"; exit 1; }
if cmp -s ids.next.txt ids.dedup.txt; then
  mv ids.next.txt ids.txt && rm -f ids.done.txt ids.dedup.txt ids.exported.txt
else
  mv ids.next.txt ids.txt && rm -f ids.done.txt ids.exported.txt
fi
EOF
```

On a bound stop:

```bash
sudo -u agentforce bash -s <<'EOF'
cd /srv/agentforce || exit 1
[ -s ids.dedup.txt ] || { echo "ids.dedup.txt is missing or empty"; exit 1; }
[ -s agentforce-repin.log ] || { echo "agentforce-repin.log is missing or empty"; exit 1; }
awk '/^Exported [0-9]+ span\(s\) for /{d[$5]} END{for (i in d) print i}' \
  agentforce-repin.log > ids.exported.txt || exit 1
awk 'FILENAME==ARGV[1]{d[$0];next} !($0 in d)' ids.exported.txt ids.dedup.txt > ids.next.txt || exit 1
[ -s ids.next.txt ] || { rm -f ids.next.txt ids.exported.txt; echo "The campaign is done"; exit 1; }
mv ids.next.txt ids.txt && rm -f ids.done.txt ids.dedup.txt ids.remaining.txt ids.exported.txt
EOF
```

Before you re-run, confirm the first ID of the new `ids.txt` does not already have a row in HoneyHive. A missing `Exported` line is not proof it never stored.

A leftover `DRY_RUN=1` walks the list, prints `Would export`, exits 0, and deletes `ids.txt` without POSTing. Clear `DRY_RUN` from `poller.env` (or the container env), restore `ids.txt` from `ids.dedup.txt`, and re-run.

These steps only create rows in the right project. They do not remove the leaked copy from the wrong project.

## Empty or 404 session fetches

Confirm Agentforce Session Tracing is on and the OTel response has spans. Salesforce documents a 72-hour window. If discovery lists IDs and every fetch returns `404`, refresh `AiAgentSession`, `AiAgentInteraction`, `AiAgentInteractionMessage`, and `AiAgentInteractionStep` in **Data Cloud > Data Streams**. A `404` on every request, including discovery, can also mean the org does not support `SALESFORCE_API_VERSION` (default `v66.0`).
