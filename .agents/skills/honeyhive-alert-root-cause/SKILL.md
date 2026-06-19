---
name: honeyhive-alert-root-cause
description: >
  Decode a HoneyHive Discover URL, query the flagged sessions and their trace trees,
  classify each finding as a true or false positive with evidence, and recommend
  specific guardrails (hooks, evaluator changes, prompt additions) to prevent recurrence.
license: MIT
metadata:
  version: "0.1.0"
  homepage: https://docs.honeyhive.ai
---

# Debug Alert Triggers via Discover URLs

When the user pastes a HoneyHive Discover URL, decode it and run a full investigation.

**Prerequisites:** The HoneyHive CLI must be installed and authenticated. See [`../honeyhive-cli/SKILL.md`](../honeyhive-cli/SKILL.md) for install, discovery, and sanity-check instructions. Run the CLI sanity check before proceeding.

## Reference Docs

- [Semantic Conventions Reference](https://docs.honeyhive.ai/v2/sdk-reference/semconv-reference) — canonical event schema, root fields, the seven structured buckets, and how attributes trigger UI behaviors
- [Framework Attribute Mapping](https://docs.honeyhive.ai/v2/sdk-reference/semconv-alignment) — how OpenTelemetry GenAI, OpenInference, and Traceloop attributes normalize into HoneyHive's schema
- [Explore Trace Data](https://docs.honeyhive.ai/v2/tracing/query-data) — programmatic query patterns, filter syntax, and pagination

## HoneyHive API Reference

This section contains the minimum API surface needed for alert investigations. For the full schema details, see the docs linked above.

### Event Schema

Every event has root fields plus seven structured buckets:

```json
{
  "event_id": "uuid",
  "session_id": "uuid",
  "parent_id": "uuid or null",
  "event_type": "session | model | tool | chain",
  "event_name": "human-readable span label",
  "source": "prod | dev | staging",
  "start_time": 1711234567000,
  "end_time": 1711234568000,
  "duration": 1000,
  "inputs": {},
  "outputs": {},
  "error": "string or null",
  "config": {},
  "metadata": {},
  "metrics": {},
  "feedback": {},
  "user_properties": {},
  "children_ids": []
}
```

**Key buckets for investigations:**
- **`inputs`**: prompts, queries, messages. Look for `chat_history` (message thread), `query` (search/retrieval), `parameters`/`tool_arguments` (function params).
- **`outputs`**: completions, responses. Look for `content` (text), `tool_calls` (function calls requested by the model), `role` (chat message role).
- **`config`**: model/tool settings. `model`, `provider`, `temperature`, `tools` (function definitions), `template` (prompt template).
- **`metadata`**: framework info, token counts. `prompt_tokens`/`completion_tokens`/`total_tokens`, `cost`, `finish_reason`, `agent_name`, `span_kind`.
- **`metrics`**: evaluator scores — the alert's monitored metric typically lives here. All sub-keys render as "Automated Evaluations" in the UI.
- **`feedback`**: human or automated annotations.

**`event_type` determines UI rendering:**
| Value | Meaning | What to look for |
|-------|---------|------------------|
| `session` | Root span grouping an invocation | `metadata.num_events`, `metadata.cost`, `metadata.total_tokens` |
| `model` | LLM call | `inputs.chat_history`, `outputs.content`, `outputs.tool_calls`, `config.model` |
| `tool` | Tool/function execution | `inputs.parameters`, `outputs`, `error` |
| `chain` | Orchestration (sub-agents, routing, retrieval) | `children_ids` to follow nested events |

### Querying Events

**CLI-first** (preferred):

```bash
# Query sessions matching filters within the alert time window
honeyhive events search \
  --filters '[{"field":"event_type","operator":"is","value":"session","type":"string"}]' \
  --date-range '{"start_time":"2025-06-01T00:00:00Z","end_time":"2025-06-02T00:00:00Z"}' \
  --limit 100 --page 1

# Query child events for a specific session
honeyhive events search \
  --filters '[{"field":"session_id","operator":"is","value":"<SESSION_ID>","type":"string"}]' \
  --date-range '{"start_time":"2025-06-01T00:00:00Z","end_time":"2025-06-02T00:00:00Z"}' \
  --limit 500 --page 1
```

Use `honeyhive events search --show-argument-schema filters` and `honeyhive events search --show-argument-schema date-range` to inspect the full schemas.

**API fallback** (when CLI is unavailable):

```
POST /v1/events/search
Authorization: Bearer $HH_API_KEY
Content-Type: application/json

{
  "filters": [
    { "field": "event_type", "operator": "is", "value": "session", "type": "string" }
  ],
  "dateRange": { "start_time": "ISO 8601 timestamp", "end_time": "ISO 8601 timestamp" },
  "limit": 100,
  "page": 1
}
```

**Important:** `dateRange` is a **top-level field** with `start_time`/`end_time` (ISO 8601) — do NOT put dates inside the `filters` array. Project scoping comes from the bearer API key, not a body field.

Filter operators: `is`, `is not`, `contains`, `not contains`, `exists`, `not exists`, `greater than`, `less than`

Filter types: `string`, `number`, `boolean`, `datetime`

Max limit per page: 1000.

### Fetching a Session Tree

**CLI-first:**

```bash
honeyhive events search \
  --filters '[{"field":"session_id","operator":"is","value":"<SESSION_ID>","type":"string"}]' \
  --date-range '{"start_time":"<ALERT_START>","end_time":"<ALERT_END>"}' \
  --limit 500 --page 1
```

**API fallback:**

```
GET /v1/sessions/{session_id}
```

Returns the nested event tree with children. Note: this endpoint requires org-scoped auth and will 401 with a project-scoped bearer API key. Prefer the CLI or `POST /v1/events/search` with a `session_id` filter.

## Decoding the URL

Discover URLs look like: `/discover/new?config=<base64>`

To decode:
```bash
echo '<base64 string>' | base64 -d | python3 -m json.tool
```

The decoded config object has this shape:
```json
{
  "type": "sessions | completions | events",
  "eventName": "specific event name (omitted if generic)",
  "filters": [{"field": "...", "value": "...", "operator": "...", "type": "..."}],
  "metric": "field name being monitored",
  "func": "avg | sum | count | min | max | median | percentile_90 | percentile_95 | percentile_99",
  "dateRange": {"$gte": "ISO timestamp", "$lte": "ISO timestamp"},
  "bucketing": "minute | hour | day | week"
}
```

## Deriving the Trigger Condition

The Discover URL config may not include the threshold filter directly. Derive it from the config:

- **`metric`** is the field being monitored (e.g., `metrics.unsafe_command_severity`)
- **`func`** is the aggregation (e.g., `avg`, `count`)
- The alert triggered because this metric crossed a threshold
- If the config already has a filter on the metric (common), use that filter directly
- If not, add one: `{"field": "<metric>", "operator": "greater than", "value": 0, "type": "number"}`

## Investigation Steps

After decoding:

1. **Summarize the alert context**: what metric, what filters, what time window, what aggregation function

2. **Query HoneyHive for matching sessions** in that time window.

   CLI-first:
   ```bash
   honeyhive events search \
     --filters '[{"field":"event_type","operator":"is","value":"session","type":"string"},{"field":"<metric>","operator":"greater than","value":"0","type":"number"}]' \
     --date-range '{"start_time":"<ALERT_START>","end_time":"<ALERT_END>"}' \
     --limit 100 --page 1
   ```

   API fallback — `POST /v1/events/search` with:
   - `dateRange` as a **top-level field** with `start_time`/`end_time` (ISO 8601) — do NOT put dates in the filters array
   - Filter `type` must be one of: `string`, `number`, `boolean`, `datetime` (not `float` or `int`)
   - Map config filters directly into the request filters, plus add `event_type: session`

3. **For each flagged session**, fetch all child events using a `session_id` filter.
   Do NOT use `GET /v1/sessions/<id>` — it requires org-scoped auth and will 401 with a project-scoped bearer API key.
   Set `limit: 500` to get the full event tree.

4. **Walk the event tree** to identify the behavior that triggered the alert:

   Use the `event_type` and `event_name` fields to navigate. The exact event names vary by source (Claude Code, Devin, custom agents, RAG pipelines, etc.) — don't assume a fixed set.

   General strategy by `event_type`:
   - **`session`**: the root event. `metadata` typically has session-level context (name, config, user properties). Start here to understand what the session was doing.
   - **`model`**: LLM calls. `inputs` has the prompt/messages, `outputs` has the completion. Check for hallucinations, policy violations in generated content, or unexpected tool-use requests.
   - **`tool`**: tool/function calls. `inputs` has the parameters the LLM requested, `outputs` has the result. This is where most unsafe *actions* surface — shell commands, API calls, file writes, database queries.
   - **`chain`**: orchestration events (sub-agents, routing, retrieval chains). `children_ids` links to the nested events. Follow these to find which step in a multi-step workflow caused the alert.

   For each event, check:
   - `error` field — non-null means something failed
   - `metrics` — the alert's monitored metric likely lives here
   - `inputs` / `outputs` — the actual content that may have triggered the evaluator

5. **Classify each finding**, distinguishing true positives from false positives:
   - **True positive / critical**: the flagged behavior is genuinely dangerous or violates policy (e.g., destructive commands, data exfiltration, unauthorized API calls, PII in outputs)
   - **True positive / low severity**: technically risky but defensible in context (e.g., a destructive action on a temp resource, an elevated-permission call that was authorized)
   - **False positive / string literal**: the flagged pattern appears inside a string constant, evaluator definition, test fixture, or documentation — the agent was *writing about* the pattern, not *executing* it
   - **False positive / safe variant**: the flagged pattern matches superficially but the actual behavior is safe (e.g., a partial keyword match, a scoped-down version of a dangerous operation)

   **To distinguish**: look at where the pattern appears in the event. Is it in `inputs.command` / `outputs.text` at the top level (likely real), or nested inside a quoted string, code block, or configuration object being *written* rather than *executed*?

6. **Recommend guardrails**:
   - Pre-execution hooks or middleware that block specific patterns before they run
   - Prompt-level instructions or system message additions to prefer safer alternatives
   - Evaluator refinements to reduce false positives (e.g., distinguish between executing a pattern vs. writing code that contains it)

## Output Format

Structure your response as:

### Alert Context
- Metric: ...
- Time window: ... to ...
- Filters: ...

### Flagged Sessions (N found)

For each:
- **Session ID**: `...` | **Verdict**: true positive / false positive
- **What happened**: one-line summary
- **Flagged behavior**: the specific events/actions that triggered the alert
- **Context**: why this behavior occurred (from surrounding events in the trace)
- **Risk level**: critical / high / medium / low

### Recommendations
- Guardrails to add
- Evaluator refinements
- Patterns to whitelist
