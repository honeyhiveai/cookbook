# Production gotchas (read before any prod-bound install)

The customer docs ship the working install. This page is the failure-mode checklist — things that work in dev and silently break in prod. Surface each item to the user as a finding before they ship.

## 1. Dependency conflicts

- `opentelemetry-api` / `opentelemetry-sdk` version drift between the HoneyHive SDK and the user's existing pinning. Run `pip show opentelemetry-api opentelemetry-sdk` (or check `package.json`/`pnpm-lock.yaml`) before installing. If the user has `opentelemetry-api < 1.20`, surface the upgrade requirement; do not upgrade unilaterally.
- `openinference-instrumentation-*` and `opentelemetry-instrumentation-*` for the same framework can both be installed; only one should be `.instrument()`-ed. If both run, attribute names diverge and dashboards split.
- LangChain `>=1.x` vs `<1.x`: the OpenInference instrumentor for LangChain has different supported versions. Check the docs page for the version pin.

## 2. Threading & async

- **Background threads / executors do not inherit the OTEL context** unless propagated explicitly. If the user spawns work via `ThreadPoolExecutor`, `asyncio.to_thread`, `multiprocessing`, etc., either propagate the context manually (`opentelemetry.context.attach`) or wrap the entry-point with the `@trace()` decorator at the right boundary. **Common bug:** spans appear truncated because the LLM call ran in a worker thread that lost context.
- In TypeScript, `async_hooks`/`AsyncLocalStorage` is the propagation mechanism. Ensure the OTEL SDK was imported at the very top of the entry-point (before any framework imports) so async-hooks is wired before user code runs.

## 3. Distributed tracing

- If the LLM app sits behind an API gateway or message queue, **trace context must propagate via headers** (`traceparent`, `tracestate`). Verify the gateway / queue isn't stripping them. For SQS/Kafka/Pub-Sub, you may need to attach the context to message attributes manually.
- For multi-service architectures, set `OTEL_PROPAGATORS=tracecontext,baggage` in every service's environment.

## 4. Memory caps

- The default `BatchSpanProcessor` queue is 2048 spans. A high-throughput agent can overflow this in seconds, dropping spans silently. Surface to the user: increase `max_queue_size` and `max_export_batch_size` if their span rate is >100/s. (`OTEL_BSP_MAX_QUEUE_SIZE`, `OTEL_BSP_MAX_EXPORT_BATCH_SIZE`.)
- Long-running processes that capture large `inputs`/`outputs` (full RAG documents, big tool I/O) accumulate per-span attribute payloads. Truncate aggressively or use the `enrich_span` pattern to capture only what's useful.

## 5. Blocking calls

- Do not put the OTLP exporter on a synchronous transport in latency-sensitive paths. The default `OTLPSpanExporter` is async; verify the user hasn't replaced it with a sync variant.

## 6. Graceful exit

The SDK handles span flushing on its own — you do **not** need to recommend an explicit `force_flush` / `flush` for normal long-running processes. The two exceptions:

- **Lambda / Cloud Run / Cloud Functions:** the runtime will SIGKILL before the queue drains unless you explicitly flush at the end of the handler. Wrap each invocation in `try/finally` and call `tracer.force_flush(timeout_millis=2000)` (or `tracer.flush()` in TS) — this is the *only* place in the skill where an explicit flush is the right answer.
- **Forking workers (gunicorn, uwsgi):** initialize the tracer **post-fork** in each worker. A pre-fork tracer leaks the parent's batch state into every child and produces session-id collisions.

## 7. Network policy & certs

- Self-hosted deployments may use a custom CA. If the user's runtime can't validate the cert, OTLP exports fail silently — the user sees no errors, just no spans appearing in the UI. Verify cert chain explicitly with `curl -v <HH_API_URL>/opentelemetry/v1/traces` before declaring success.
- Egress firewalls: the OTLP HTTP endpoint is `:443` outbound to the user's deployment host (default `api.dp1.us.honeyhive.ai`, or the customer's dedicated/self-host URL). If the user is behind a strict egress policy, surface the URL + port to their network team.
- HTTP proxies: `HTTPS_PROXY` is honored by the default exporter, but `NO_PROXY` must include the HoneyHive domain when the proxy is corporate-only.

## 8. PII & content

- The OpenInference / Traceloop instrumentors capture **full message content by default**. For regulated workloads (PHI, PCI), set `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=false` (Traceloop) or use the OpenInference `record_inputs=False` flag. Surface this to the user as a finding before any prod-bound install if they handle regulated data.

## 9. Sampling

- `TraceIdRatioBased(0.1)` (10% sampling) at the head will silently drop 90% of agent runs. For LLM workloads we recommend `ParentBased(AlwaysOn)` because each session is independently valuable. Do not change the user's sampler unless they ask; surface as a finding.

## 10. SDK version compatibility

- Pin `honeyhive>=<X>,<<Y>` based on the framework's required range. The matrix is on the framework's docs page. If the user's `honeyhive` is below the minimum for their framework, surface the upgrade — do not upgrade unilaterally.
