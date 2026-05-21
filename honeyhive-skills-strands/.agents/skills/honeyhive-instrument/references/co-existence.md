# Coexisting with a non-HoneyHive `TracerProvider`

`HoneyHiveTracer.init(...)` constructs an **independent** `TracerProvider` for HoneyHive — it does **not** call `trace.set_tracer_provider(...)` globally. The user's existing global provider (Datadog, New Relic, vendor-native) is untouched. There is no hijack risk.

The real question with a pre-existing provider is **not** "will HoneyHive conflict?" — it's **"do you want the spans currently going to the user's other vendor to ALSO go to HoneyHive?"**

## Decision tree

### 0. Is the user's "existing provider" actually real?

Before assuming coexistence is needed, check what `trace.get_tracer_provider()` (or the language equivalent) actually returns. The OTel API ships a *proxy* / *no-op* `TracerProvider` as the default — it returns spans that go nowhere. Many libraries import the OTel API without configuring a real SDK, so `get_tracer_provider()` returns this placeholder.

Signals it's a no-op / placeholder:

- The class name contains `Proxy`, `NoOp`, `Noop`, or `Default`.
- No `SpanProcessor` is attached / no `add_span_processor` calls in the user's code.
- No exporter is configured anywhere in the codebase.
- The user can't name the backend their spans are going to.

**If non-functional:** there's nothing to coexist with. `HoneyHiveTracer.init(...)` runs as if greenfield. Done.

### 1. Real provider, no dual-export needed

The simplest path: HoneyHive's tracer runs alongside the existing one, doing its own thing. New instrumentors you wire up for HoneyHive get `tracer_provider=tracer.provider` (the HoneyHive-private provider); existing auto-instrumentors that attach to the global keep flowing to the user's other vendor. **Two pipelines, no overlap, no shared state.** Pick this when the user only wants HoneyHive on the LLM/agent surface and is fine leaving their Datadog/New Relic pipeline alone for everything else.

### 2. Real provider, dual-export wanted

The user wants spans currently going to their other vendor to ALSO appear in HoneyHive — same auto-instrumentors, two backends. Two sub-cases:

- **Provider exposes a way to add another span processor** (`add_span_processor` / `addSpanProcessor` / equivalent — most OTel SDK providers do): add a HoneyHive `BatchSpanProcessor` (with the OTLP exporter pointing at HoneyHive's collector) to the existing provider. Spans flow to both backends from the same provider. Do **not** call any global tracer-provider setter.
- **Provider does not expose this** (some vendor-wrapped agent shims hide or lock the internal pipeline): the OTEL pipeline can't carry HoneyHive too. Fall back to **Path B's manual approach** — instrument with the HoneyHive REST API directly (`POST /session/start` to open a session, `POST /events` per model call). The user's OTEL pipeline is left untouched for their other vendor; HoneyHive runs as a parallel, non-OTEL instrumentation. Surface this as a finding so the user knows why they're not getting auto-instrumented spans on the HoneyHive side.

### 3. Refuse cases

- **Existing provider has a custom `SpanProcessor` that mutates attributes.** Mutating processors will rewrite gen_ai/openinference attributes and the spans HoneyHive receives won't match dashboards. Refuse dual-export; ask the user which provider should be source-of-truth.
- **User's policy forbids dual-export.** Don't wire HoneyHive into the existing pipeline; either run HoneyHive independently (decision tree §1) or skip.

## Anti-patterns

- **Don't wrap the user's provider in a `MultiplexingTracerProvider` that you wrote yourself.** OTEL spec doesn't define multiplexing semantics; downstream tools may treat it as a bug. Use one provider with two processors instead.
- **Don't change the user's sampler.** If their existing provider uses `TraceIdRatioBased(0.1)`, adding HoneyHive's processor inherits that sampling. That's the correct behavior — do not "fix" it.
- **Don't write code that globally registers HoneyHive as the source-of-truth provider** (`trace.set_tracer_provider(hh.provider)`). The SDK doesn't do this; the instrumentation layer shouldn't either.
