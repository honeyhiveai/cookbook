# Shareable Links

Generate shareable HoneyHive frontend URLs so the user can jump directly to a trace or experiment run in the UI.

## Trace Link

Opens a specific session or event in the traces view with the event drawer pre-opened.

**Format:**
```
{base_url}/p/{projectId}/traces/{type}?event={eventId}&range={dateRange}
```

| Placeholder | Value |
|---|---|
| `base_url` | `https://app.us.honeyhive.ai` (multi-tenant), `https://app.<tenant>.us.honeyhive.ai` (dedicated), or fully custom for self-hosted |
| `projectId` | The HoneyHive project ID (e.g. `peQ9-_5k2zXezKJ_cwO20KYx`) |
| `type` | `sessions`, `completions`, or `events` |
| `eventId` | The `session_id` or `event_id` to open |
| `dateRange` | Optional. Valid values: `1d`, `3d`, `7d`, `30d`, `90d`, `2w`, `4w`, `8w`, `12w`, `24w`, `3m`, `6m`, `12m`, `AllTime` |

**Type selection:**
- `sessions` — top-level session traces (most common)
- `completions` — individual LLM model calls
- `events` — all event types (tool calls, chains, generic spans)

**Examples:**
```
https://app.us.honeyhive.ai/p/peQ9-_5k2zXezKJ_cwO20KYx/traces/sessions?event=23e7b0cb-34cd-4bd6-859a-5b89156f2cc2&range=7d
https://app.us.honeyhive.ai/p/peQ9-_5k2zXezKJ_cwO20KYx/traces/completions?event=a1b2c3d4-5678-9012-abcd-ef1234567890
```

If `dateRange` is omitted, the frontend defaults to `7d`.

## Experiment Run Link

Opens a specific experiment run with its results and evaluator scores.

**Format:**
```
{base_url}/p/{projectId}/experiments/runs/{runId}
```

| Placeholder | Value |
|---|---|
| `base_url` | `https://app.us.honeyhive.ai` (multi-tenant), `https://app.<tenant>.us.honeyhive.ai` (dedicated), or fully custom for self-hosted |
| `projectId` | The HoneyHive project ID |
| `runId` | The experiment run ID returned by `honeyhive experiments` or `evaluate()` |

**Example:**
```
https://app.us.honeyhive.ai/p/peQ9-_5k2zXezKJ_cwO20KYx/experiments/runs/b7f3e2a1-9c84-4d56-a123-456789abcdef
```

## When to Emit Links

| Trigger | Which link |
|---|---|
| After a verification smoke run produces a `session_id` (instrumentation) | Trace link for the verified session |
| After `evaluate()` or `honeyhive experiments` returns a `run_id` (evaluation) | Experiment run link; optionally trace links for individual datapoints |
| When presenting a failing session to the user or validating a fix (debugging) | Trace link for the failing/fixed session |

## Constructing the URL Programmatically

```bash
# Bash one-liner (trace link)
BASE_URL="https://app.us.honeyhive.ai"  # multi-tenant; use app.<tenant>.us.honeyhive.ai for dedicated
echo "${BASE_URL}/p/${PROJECT_ID}/traces/sessions?event=${SESSION_ID}&range=7d"

# Bash one-liner (experiment run link)
echo "${BASE_URL}/p/${PROJECT_ID}/experiments/runs/${RUN_ID}"
```

```python
# Python
base = "https://app.us.honeyhive.ai"  # multi-tenant; use app.<tenant>.us.honeyhive.ai for dedicated
trace_url = f"{base}/p/{project_id}/traces/sessions?event={session_id}&range=7d"
run_url = f"{base}/p/{project_id}/experiments/runs/{run_id}"
```

## Notes

- These URLs use the canonical query-param format for traces. The frontend also supports a legacy path-segment format (`/traces/{type}/{event_id}/{dateRange}`) via backwards-compat redirects, but always prefer the canonical format.
- `base_url` varies by deployment: `app.us.honeyhive.ai` (multi-tenant), `app.<tenant>.us.honeyhive.ai` (dedicated), or fully custom (self-hosted).
- Project IDs use the character set `[A-Za-z0-9_-]` and do not need URL encoding.
- Event/session IDs may contain characters that need encoding; use `encodeURIComponent` (JS) or `urllib.parse.quote` (Python) if constructing from untrusted input.
