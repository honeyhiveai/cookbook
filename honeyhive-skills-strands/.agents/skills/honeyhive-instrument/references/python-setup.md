# Python setup

For Python apps using `honeyhive` + a framework (OpenAI, Anthropic, LangChain, LlamaIndex, DSPy, CrewAI, AutoGen, Semantic Kernel, Strands, Bedrock, Google ADK, MCP, etc.).

Assumes [`network-validation.md`](network-validation.md) has confirmed reachability and [`runtime-validation.md`](runtime-validation.md) has produced findings (`framework`, `framework_version`, `instrumentor_family`, `existing_hh_wiring`, `existing_otel_provider`, etc.). This file consumes those findings rather than re-detecting.

The skill's job in Python has five parts: **(0)** translate runtime-validation findings into a concrete dependency + instrumentor decision and install only what's missing; **(1)** decide whether the user's framework needs an external instrumentor or already emits OTel natively; **(2)** put `tracer.create_session(...)` (or `acreate_session(...)`) at the right place in the user's code; **(3)** handle distributed trace propagation when the app spans services — or sidestep it via the GUID shortcut; **(4)** verify everything against the framework + app shape.

## Step 0 — Translate runtime-validation findings into a setup plan

Inputs (from [`runtime-validation.md`](runtime-validation.md) output):

- `framework`, `framework_version`
- `instrumentor_family` ∈ {`openinference`, `traceloop`, `none`, `conflict`}
- `existing_hh_wiring` (file:line, or `none`)
- `existing_otel_provider` (`none` / `proxy-noop` / `real:<vendor>` / `real:custom-mutating`)

Decisions:

| Finding | Action |
|---|---|
| `instrumentor_family = conflict` | **Stop.** Both OpenInference and OpenLLMetry/Traceloop are pinned. Surface to the user; ask which family to keep. Never silently pick. |
| `instrumentor_family = openinference` | Continue with OpenInference. If `openinference-instrumentation-<framework>` is missing for the detected framework, install it explicitly (`pip install openinference-instrumentation-<framework>`). Do not silently mutate a manifest the user did not commit. |
| `instrumentor_family = traceloop` | Continue with OpenLLMetry/Traceloop. Same install rules. |
| `instrumentor_family = none` | Default to OpenInference for new Python apps unless the framework is OTel-native (Step 1). |
| `existing_hh_wiring != none` | **Reuse the existing tracer instance.** Skip the `HoneyHiveTracer.init(...)` step in Phase 1; the rest of setup augments the existing wiring (placing `create_session` calls, etc.). |
| `existing_otel_provider = real:custom-mutating` | **Refuse dual-export.** A mutating SpanProcessor will rewrite gen_ai/openinference attributes — surface to the user before proceeding. See [`co-existence.md`](co-existence.md). |
| `existing_otel_provider = real:<vendor>` (Datadog/New Relic) | Ask the user whether they want dual-export. If yes, follow [`co-existence.md`](co-existence.md) §2. If no, run HoneyHive's tracer independently (the SDK builds its own provider). |

If `honeyhive` itself is missing from the manifest, install it explicitly: `pip install honeyhive`. Document the env vars (`HH_API_KEY`, `HH_API_URL`, `HH_PROJECT`) in the user's setup block so the install is reproducible.

**Never bump the framework's version** to make instrumentation work. If the pinned version is incompatible with the chosen instrumentor, surface as a finding and let the user decide whether to upgrade.

## Step 1 — OTel-native vs needs-an-instrumentor

Not all Python LLM frameworks emit OpenTelemetry spans natively. The instrumentation strategy diverges:

- **Framework already emits OTel spans**: just `HoneyHiveTracer.init(...)` is enough; the SDK's tracer provider picks them up via the OTel SDK. **Do not attach an external instrumentor on top of native spans** — you'll get duplicate or attribute-conflicting spans. Validate by running the user's app once with HoneyHive init only and confirming spans appear in the UI.
- **Framework does not emit OTel spans**: attach the matching external instrumentor — `openinference-instrumentation-<framework>` (default) or `opentelemetry-instrumentation-<framework>` (if the user is already on OpenLLMetry). Pick the family already pinned in the user's deps; do not switch families.

Some frameworks have *partial* native OTel support (e.g. only certain code paths emit spans). When in doubt, run the smoke test both ways (with and without the external instrumentor) and pick whichever produces the cleaner trace structure per [`success.md`](../success.md).

## Step 2 — Place `tracer.create_session()` / `tracer.acreate_session()` correctly

`HoneyHiveTracer.init()` configures the tracer once at process startup. **Sessions** are opened per logical unit of work via `tracer.create_session(...)` (sync) or `tracer.acreate_session(...)` (async). The session id lands in OpenTelemetry baggage so the span processor associates spans with the right session even across concurrent requests.

The skill must locate the right place in the user's code to call create_session. The "right place" depends on the app shape:

| App shape | Where to call `create_session` |
|---|---|
| **Web service** (FastAPI / Flask / Django / Starlette) | Middleware that runs per request — open the session at request entry, before any LLM call. The async variant (`acreate_session`) is required in async middleware. |
| **CLI agent / one-shot script** | At the top of `main()`, or wherever the user-facing entry happens. One session per invocation. |
| **Long-running worker** (Celery, RQ, SQS poller, Kafka consumer, custom loop) | At the start of each unit of work — per message, per job, per polled batch. **Never** at module load. |
| **Streaming / chat session** | Whenever a new conversation starts (often on the first user message). Cache the session id in conversation state so subsequent messages can reuse it. |
| **Notebook / interactive REPL** | Per cell or per logical experiment — the user picks. |

**Anti-patterns to refuse:**

- Calling `create_session` at module load (`tracer.create_session()` next to `HoneyHiveTracer.init(...)`) — this opens a single session for the whole process, defeating per-request isolation.
- Calling `create_session` inside a tight loop where each iteration is *not* logically a new session.
- Reusing a session id across unrelated requests in a multi-tenant process.

### `inputs` / `metadata` at session start

When you call `create_session`, populate the `inputs` arg with the user-facing query (or a representative payload) and `metadata` with anything that helps debugging — request path, user id, feature flags. This is what becomes the session's "head" event and what the [`success.md`](../success.md) "user's original query is easy to identify" rubric grades against.

## Step 3 — Distributed trace context propagation

When the user's LLM/agent flow spans multiple services (microservices, queue → worker handoffs, cross-process pipelines), spans from each service need to land in the **same** HoneyHive session. Two approaches:

### (A) OTel context propagation (orthodox)

- Inbound HTTP middleware extracts W3C `traceparent` + `baggage` headers, attaches them to the local OTel context.
- Outbound HTTP clients inject the same headers.
- HoneyHive's session id rides as a baggage attribute (`honeyhive.session_id`); the receiving service reads it with `skip_api_call=True` to attach to the existing session rather than creating a new one:

  ```python
  # Receiving service (mid-session entry):
  inbound_session_id = baggage.get_baggage("honeyhive.session_id")
  if inbound_session_id:
      tracer.create_session(session_id=inbound_session_id, skip_api_call=True)
  else:
      tracer.create_session(...)  # this service is the session's origin
  ```

- Set up propagators globally: `opentelemetry.propagators.composite.CompositePropagator([TraceContextTextMapPropagator(), W3CBaggagePropagator()])`.

- Watch for context loss across `asyncio.to_thread`, `ThreadPoolExecutor`, `multiprocessing` — those don't auto-propagate. Either wrap the entry-point or manually `attach(context)` inside the worker.

### (B) GUID shortcut (often simpler)

If the user's app already has a request-id / correlation-id / conversation-id propagated end-to-end (X-Request-Id header, message envelope field, conversation_id in the payload), **skip baggage entirely**: each service derives the HoneyHive session_id from that GUID and calls `create_session(session_id=..., skip_api_call=True)` (after the first service, which makes the API call to actually create the session row).

- If the GUID is already a UUID, pass it directly.
- If it's not (numeric id, opaque external id), convert it deterministically: `str(uuid.uuid5(uuid.NAMESPACE_URL, raw_guid))`. Same input → same UUID → all services in the chain end up with the same session_id without any header propagation setup.

This sidesteps the *whole* baggage / propagator / context-loss debugging surface. The tradeoff: the user must already have a propagated GUID (or be willing to add one to their request envelope). Most modern services do — request IDs are table stakes for debugging anyway.

Recommend (B) when the user has a GUID; recommend (A) when they don't and a structural addition isn't worth it.

## Step 4 — Verify

Before declaring success, confirm:

- `HoneyHiveTracer.init(...)` is called exactly once at process startup, with `api_key` + `project` from env vars (never literal). For dedicated/self-host, `server_url` set per [`dedicated-deployments.md`](dedicated-deployments.md).
- The chosen integration matches the framework's OTel story (Step 1):
  - OTel-native framework → no external instrumentor attached.
  - Non-OTel-native framework → exactly one instrumentor attached, family matches deps, `instrument(tracer_provider=tracer.provider)` called.
- `tracer.create_session(...)` / `acreate_session(...)` lands at every session boundary — middleware for web, `main()` for CLI, per-message for workers. Inputs and metadata populated.
- For multi-service apps: either propagators are set up globally (Approach A) or every service is calling `create_session(session_id=<derived from shared GUID>, skip_api_call=True)` (Approach B).
- The SDK auto-flushes — do **not** add `tracer.force_flush()` as a general practice. The single exception is Lambda / serverless (see [`prod-gotchas.md`](prod-gotchas.md) §6).
- Run the smoke test once with one real LLM call. Inspect the resulting trace against [`success.md`](../success.md): is the trace structure easy to debug? Are agent/tool/LLM events nested correctly? Is the user query identifiable?

If the smoke trace is messy (deeply hidden LLM calls, wrong nesting, missing tool linkage), the integration is mechanically correct but qualitatively wrong — circle back and adjust the instrumentor choice or session-boundary placement.
