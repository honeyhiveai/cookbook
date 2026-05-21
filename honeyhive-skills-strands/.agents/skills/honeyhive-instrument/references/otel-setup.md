# Native OTel setup (any language)

For Go, Rust, Java, .NET, C++, or any app with a fully bespoke OpenTelemetry setup that the Python/TS HoneyHive SDKs cannot wrap. Same shape as Python setup in spirit — early init, session-boundary placement, span capture on key steps, distributed propagation — but every hook is built from the user's existing OTel SDK rather than from the HoneyHive SDK.

Assumes [`network-validation.md`](network-validation.md) has confirmed reachability and [`runtime-validation.md`](runtime-validation.md) has produced findings (`language`, `runtime_version`, `existing_otel_provider`). This file consumes those findings rather than re-detecting.

> **This recipe lives here, not on docs.honeyhive.ai (yet).** Until the public integrations tab publishes a Native OTel page, this file is the source of truth for the OTLP attribute contract.

## TL;DR

| | Value |
|---|---|
| **OTLP HTTP endpoint** | `https://api.dp1.us.honeyhive.ai/opentelemetry/v1/traces` (dedicated / self-host customers use their own per-tenant host — see [`dedicated-deployments.md`](dedicated-deployments.md)) |
| **Auth header** | `Authorization: Bearer <PROJECT API KEY>` — keys are scoped to a single project; no per-span project routing needed |
| **Session correlation** | Set baggage attributes (`honeyhive.session_id`, optionally `honeyhive.session_name`) at the session boundary, OR run a small custom `SpanProcessor` that stamps them at export time |

## Step 0 — Translate runtime-validation findings into a setup plan

Inputs (from [`runtime-validation.md`](runtime-validation.md) output):

- `language` (Go / Rust / Java / .NET / C++ / Python-going-via-OTel / TS-going-via-OTel)
- `runtime_version`
- `existing_otel_provider` — most relevant for this path; whether the user already has an OTel SDK provider configured for their other backend
- `existing_otel_provider`'s sampler + processor list (if real)

Decisions:

| Finding | Action |
|---|---|
| `existing_otel_provider = none` or `proxy-noop` | Greenfield install: register a real `TracerProvider` with `BatchSpanProcessor` + OTLP exporter pointing at HoneyHive (Step 1). |
| `existing_otel_provider = real:<vendor>` (Datadog/New Relic/etc.) | Do **not** replace it. Either add a HoneyHive `BatchSpanProcessor` to the existing provider for dual-export (most languages support `addSpanProcessor` on a live provider), or surface a refusal if it doesn't expose that hook (rare for native OTel SDKs; common for closed-source agent shims). See [`co-existence.md`](co-existence.md). |
| `existing_otel_provider = real:custom-mutating` | **Refuse dual-export.** A mutating `SpanProcessor` will rewrite gen_ai/openinference attributes — surface to the user before proceeding. |
| `existing_otel_provider`'s sampler is non-`AlwaysOn` (e.g. `TraceIdRatioBased(0.1)`) | Surface to the user — head-based sampling will silently drop most LLM sessions. Recommend `ParentBased(AlwaysOn)`. **Don't change the sampler unilaterally.** |

OTel SDK packages the user already has installed determine which of the language column patterns in the rest of this file applies. Don't add extra OTel SDK packages unless the user genuinely lacks them — assume the runtime-validation findings tell you what's there.

**Never bump OTel SDK versions** to make HoneyHive's exporter work. If `OTLPSpanExporter` types or processor interfaces have shifted across SDK versions, surface the version mismatch and let the user decide whether to upgrade.

## Step 1 — Early initialization

Initialize the user's OTel SDK at app startup, before any traced code runs. Register:

- An OTLP HTTP exporter pointing at HoneyHive's collector with the `Authorization: Bearer <project key>` header.
- A `BatchSpanProcessor` wrapping that exporter (almost always — synchronous exporters belong only in tests).
- *Either* a small custom `SpanProcessor` that stamps `honeyhive.*` attributes (the [span-processor pattern](#span-processor-pattern) below), *or* nothing extra if you're going to set baggage at the session boundary instead (Step 2).

Same constraint as Python and TS: this happens once at process startup. **Never inside a request handler**, never lazily — the OTel SDK gets unhappy if a real provider is set after a no-op default has been observed.

## Step 2 — Locate the session boundary; set `honeyhive.session_id`

The hardest part of native OTel is finding the right place in the user's code where a session **logically begins or resumes** and stamping the session id there. Same map as Python's `create_session` placement:

| App shape | Where to stamp `honeyhive.session_id` |
|---|---|
| **HTTP service** | Per-request middleware that runs at handler entry |
| **CLI / one-shot** | At the top of `main()` |
| **Worker / consumer** | At the start of each unit of work (per message, per job, per polled batch) |
| **Multi-service mid-session entry** | Wherever the request enters this service (continuation of a session that started elsewhere) |

Two ways to actually attach the session id:

### (a) Baggage (orthodox)

Set `honeyhive.session_id` (and optionally `honeyhive.session_name`) as OTel baggage entries at the session boundary. Configure a baggage span processor (most OTel SDKs ship one as `BaggageSpanProcessor` or equivalent) so the baggage flows onto every span emitted within that context. This is the cleanest pattern for distributed apps because the baggage propagates across services automatically when W3C `baggage` headers are wired up.

### (b) Custom span processor — the GUID shortcut <a name="span-processor-pattern"></a>

If the user already has a request-id / correlation-id / conversation-id propagated end-to-end, **skip baggage entirely**. Run a small `SpanProcessor` whose `OnStart` (or `OnEnd`) reads that id off the span attributes and stamps it as `honeyhive.session_id` plus `honeyhive.session_auto_create=true`:

```
class HoneyHiveProcessor(joining_attribute_key):
    def OnEnd(span):
        joining_value = span.attributes.get(joining_attribute_key)
        if joining_value is not None:
            span.set_attribute("honeyhive.session_id", joining_value)
        span.set_attribute("honeyhive.session_auto_create", true)
```

The processor takes one config knob — the joining attribute key (e.g. `"session.id"`, `"conversation.id"`, `"gen_ai.session.id"`, `"chat_id"`, or any custom name the app already emits). Same input → same id → all services in the chain end up with the same HoneyHive session without baggage / W3C-tracecontext setup.

If the joining attribute is absent on a given span, only stamp `honeyhive.session_auto_create=true` — HoneyHive's resolution chain (`traceloop.association.properties.session_id` → `session.id`) takes over.

| Language | `SpanProcessor` interface | Where to register |
|---|---|---|
| Go    | `sdktrace.SpanProcessor` (`OnStart`/`OnEnd`) | `sdktrace.WithSpanProcessor(...)` on the provider |
| Java  | `io.opentelemetry.sdk.trace.SpanProcessor` | `SdkTracerProvider.builder().addSpanProcessor(...)` |
| .NET  | `BaseProcessor<Activity>` | `OpenTelemetrySdk.CreateTracerProviderBuilder().AddProcessor(...)` |
| Rust  | `opentelemetry_sdk::trace::SpanProcessor` | `TracerProvider::builder().with_span_processor(...)` |
| Python | `opentelemetry.sdk.trace.SpanProcessor` | `TracerProvider.add_span_processor(...)` (only when Python is genuinely going through this native-OTel path; otherwise prefer [`python-setup.md`](python-setup.md)) |

Register **before** the `BatchSpanProcessor` so attributes are stamped before the export queue serializes the span.

> **Recommend (b) when the user has a propagated GUID; recommend (a) when they don't and a structural addition isn't worth it.** OTTL transforms in an OpenTelemetry Collector are a third option if the user's app exports through a collector — same logic, expressed in collector config; see <https://opentelemetry.io/docs/collector/transforming-telemetry/>.

## Step 3 — Span capture on key processing steps

Once the session boundary is stamped, the actual *spans* still have to be there. Native OTel doesn't auto-instrument LLM calls — wrap each meaningful step yourself:

- LLM call → span with `gen_ai.system`, `gen_ai.request.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, plus `inputs`/`outputs` attributes for the message history and response.
- Tool call → span with the tool name, `inputs`, `outputs`, and `event_type=tool` (or the OTel equivalent attribute).
- Agent step / orchestration node → span wrapping the LLM + tool calls underneath, with the agent name in the span name.
- Retrieval step → span with the query, retrieved doc ids, and ranking.

These are what the [`success.md`](../success.md) rubric grades against — the trace will look mechanically correct without them but qualitatively empty.

## Step 4 — Distributed trace context propagation (or sidestep it)

When the app spans services, propagation matters:

### Approach A — W3C tracecontext + baggage propagators

Configure global propagators (`OTEL_PROPAGATORS=tracecontext,baggage` env var, or per-language equivalent). Every outbound HTTP / gRPC / message-bus client must inject; every inbound handler must extract. Async work that crosses thread / process boundaries (executors, queues) must propagate context manually.

### Approach B — GUID shortcut (often simpler)

If the user has a propagated correlation id already, the custom span processor in Step 2(b) reads it on every service in the chain. No baggage propagators, no W3C tracecontext setup, no debugging cross-`async_hooks` context loss. Same caveat as Python — needs an existing propagated GUID, but most modern services have one.

## All `honeyhive.*` protocol attributes

`honeyhive.*` attributes are *protocol* attributes — they control routing and grouping but are not stored as user-visible span attributes (they will not appear in the UI's span attribute list).

| Attribute | Type | Required | Notes |
|---|---|---|---|
| `honeyhive.session_id` | string | required for span→session association | Highest-priority of the resolution chain. Falls back to `traceloop.association.properties.session_id` → `session.id`. |
| `honeyhive.session_auto_create` | bool | required for auto-correlation | Tells HoneyHive to create a session automatically from the span's `session_id` and timestamps. Without it, a span with an unknown `session_id` is accepted (200 OK) but no session is created — spans appear orphaned in the UI. Safe to stamp on every span; duplicates are no-ops. |
| `honeyhive.session_name` | string | optional | Defaults to `"Session"` on auto-create. Set this only when you want a specific human-readable name in the UI. |
| `honeyhive.source` | string | optional | E.g. `"prod"`, `"dev"`, `"ci"`. Defaults to `"otlp"`. |
| `honeyhive.experiment_metadata` | string (JSON) | optional | Used by the experiments runner to attach a span to a specific experiment run. |

## Step 5 — Verify

Before declaring success, confirm:

- OTel SDK init runs once at app startup; the OTLP exporter targets the right HoneyHive host (multi-tenant default `api.dp1.us.honeyhive.ai`, or the dedicated/self-host URL per [`dedicated-deployments.md`](dedicated-deployments.md)).
- Authentication header uses the project API key from an env var (never a literal).
- Session-boundary stamping is wired (Step 2) — either baggage at the boundary or a custom span processor reading a joining attribute.
- Key processing steps are wrapped as spans with appropriate semconv attributes (Step 3).
- For multi-service apps: either propagators are set up globally (Approach A) or every service's span processor is reading the same propagated GUID (Approach B).
- Sampling: if the existing OTel setup uses head-based sampling (`TraceIdRatioBased(0.1)`), HoneyHive only receives that fraction of agent runs. For LLM workloads recommend `ParentBased(AlwaysOn)`. Don't change the user's sampler unilaterally; surface as a finding.
- Run a smoke test. Inspect the resulting trace against [`success.md`](../success.md): is the trace structure easy to debug? Are session boundaries visible? Do LLM/tool/agent spans nest correctly?

## Common failures

- **Spans return 200 but never appear in the UI.** `honeyhive.session_id` resolved (directly or via the fallback chain) but `honeyhive.session_auto_create` is missing — HoneyHive has no signal to create a session from. Make sure the span processor is stamping `auto_create=true` on every span (or call `POST /session/start` separately).
- **Each span shows up as its own session.** Different `session_id` values across spans the user expected to group together. Check the joining-attribute key — is it actually present and stable across the calls you expect to group? Log the joining value from inside the processor for one run to confirm.
- **401 Unauthorized.** Missing `Bearer ` prefix, empty key env var, or the key was revoked. Use a project API key — the OTLP endpoint requires project scope.
- **TLS errors against the deployment host.** Self-host certs may need a custom CA bundle; verify with `curl -v` before declaring success.
