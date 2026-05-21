---
name: honeyhive-instrument
description: >
  Instrument an AI application with HoneyHive tracing. Use when the user wants
  to add observability, capture traces, set up the SDK, configure exporters,
  or wire OpenTelemetry-compatible instrumentation for an agent, RAG pipeline,
  or LLM application. Triggers on phrases like "add tracing", "instrument my
  app", "wire up HoneyHive", "set up the SDK", "capture spans", "OTEL
  exporter", or any mention of `HoneyHiveTracer.init`, `@honeyhive/api-client`,
  `client.sessions.startSession`, `client.events.createEvent`, or
  `OpenInference`/`Traceloop` instrumentors targeting HoneyHive.
license: MIT
metadata:
  version: "0.1.0"
  homepage: https://docs.honeyhive.ai
---

# HoneyHive Instrument

Wire HoneyHive tracing into a user's application with a small, surgical edit set: initialize the tracer, attach an instrumentor for their LLM/agent framework, and verify spans flush. Be **progressive** — start with discovery, only do the work the user actually asked for.

> **You are an instrumentation surgeon, not a rewriter.** The user has working code. Add tracing in the smallest number of edits possible. Never refactor unrelated code, never change framework versions, never strip features.

## Phase 0 — Validation (run in order; stop on failure)

Validation comes before setup. Two checks, ordered: **network first** (cheap, catches the largest class of failures), then **runtime** (deterministic detection that feeds Phase 1 setup directly). If either fails, surface to the user and stop — do not improvise.

1. **Network validation.** Confirm `HH_API_KEY` and `HH_API_URL` are sourced from environment (no literal keys in code), then run a `curl` reachability check against `<HH_API_URL>/projects` with `Authorization: Bearer <key>`. 200 = good; 401/403/404/connection error = stop and surface. TLS chain check for self-host. Full procedure + interpretation table: [references/network-validation.md](references/network-validation.md). The output (validated `HH_API_KEY`, `HH_API_URL`, `deployment_type`) feeds the rest of the skill.

2. **Runtime validation.** Identify the right sub-tree (in a monorepo, the LLM app may live in a subfolder; ask the user if ambiguous — all subsequent reads and edits scope here). Then detect: language + runtime version, framework + version, instrumentor family (Python: OpenInference vs OpenLLMetry/Traceloop), pre-existing HoneyHive wiring (`HoneyHiveTracer.init` / `new Client()`), pre-existing global OTel `TracerProvider` (vendor + sampler + processor list). Output structured findings the Phase 1 setup file consumes — language-specific setup never re-detects from scratch. Procedure: [references/runtime-validation.md](references/runtime-validation.md).

## Phase 1 — Setup (load the language-specific reference; follow it end-to-end)

HoneyHive instrumentation differs by language. Pick the path that matches the runtime-validation findings — do **not** default to a path the user's code does not already point at — then load the matching setup reference and follow it. Each setup file consumes Phase 0's findings, makes the dependency + instrumentor decision, places session boundaries, handles distributed propagation, and runs language-level verification. The setup file is the durable per-language playbook.

- **A. Python** — [`references/python-setup.md`](references/python-setup.md). Translate runtime-validation findings into a dependency plan; decide native-OTel vs external instrumentor (OpenInference / Traceloop, never both); place `tracer.create_session(...)` / `tracer.acreate_session(...)` at the right session boundary; propagate OTel context across services or sidestep via a GUID shortcut.
- **B. TypeScript** — [`references/ts-setup.md`](references/ts-setup.md). Build a small structured-logger wrapper around `@honeyhive/api-client` (module-level singleton + `AsyncLocalStorage`); take the user's correlation GUID at session start; structure event payloads around OpenTelemetry gen_ai semantic conventions.
- **C. Native OTel exporter** (Go, Rust, Java, .NET, or any app with a bespoke OTEL setup) — [`references/otel-setup.md`](references/otel-setup.md). Early init; locate session-boundary point; set baggage (`honeyhive.session_id` / `honeyhive.session_name`) or run a small custom `SpanProcessor` that stamps it; instrument key processing steps; propagate distributed trace context or sidestep via a GUID shortcut.

For Python frameworks first-class on docs, also pull the framework's docs page for the exact install + minimal-integration block — copy verbatim, adapt to the user's entry-point, do not paraphrase. Index:

- **Tracing quickstart** — <https://docs.honeyhive.ai/v2/introduction/tracing-quickstart>
- **OpenAI** — <https://docs.honeyhive.ai/v2/integrations/openai>
- **Anthropic** — <https://docs.honeyhive.ai/v2/integrations/anthropic>
- **Azure OpenAI** — <https://docs.honeyhive.ai/v2/integrations/azure_openai>
- **AWS Bedrock** — <https://docs.honeyhive.ai/v2/integrations/aws_bedrock>
- **Gemini** — <https://docs.honeyhive.ai/v2/integrations/gemini>
- **LangChain** — <https://docs.honeyhive.ai/v2/integrations/langchain>
- **LangGraph** — <https://docs.honeyhive.ai/v2/integrations/langgraph>
- **LiteLLM** — <https://docs.honeyhive.ai/v2/integrations/litellm>
- **DSPy** — <https://docs.honeyhive.ai/v2/integrations/dspy>
- **CrewAI** — <https://docs.honeyhive.ai/v2/integrations/crewai>
- **AutoGen** — <https://docs.honeyhive.ai/v2/integrations/autogen>
- **OpenAI Agents SDK** — <https://docs.honeyhive.ai/v2/integrations/openai-agents>
- **Claude Agent SDK** — <https://docs.honeyhive.ai/v2/integrations/claude-agent-sdk>
- **Google ADK** — <https://docs.honeyhive.ai/v2/integrations/google-adk>
- **Pydantic AI** — <https://docs.honeyhive.ai/v2/integrations/pydantic-ai>
- **Semantic Kernel** — <https://docs.honeyhive.ai/v2/integrations/semantic-kernel>
- **Strands Agents** — <https://docs.honeyhive.ai/v2/integrations/strands>

Plus the SDK + semconv references (especially for Path C and verification):

- **Python SDK** — <https://docs.honeyhive.ai/v2/sdk-reference/python-sdk-ref>
- **TypeScript SDK** — <https://docs.honeyhive.ai/v2/sdk-reference/typescript-sdk-ref>
- **Semantic-convention reference** — <https://docs.honeyhive.ai/v2/sdk-reference/semconv-reference>
- **Framework attribute mapping** — <https://docs.honeyhive.ai/v2/sdk-reference/semconv-alignment>

**Confirm the path with the user before adding dependencies.** If the user's framework isn't on the index above, follow the doc-gap protocol in Phase 2 step 3.

## Phase 2 — Verify locally

Per-language wiring + verification lives in the language reference (Phase 1). At the SKILL.md level the verification loop is:

1. **Smoke run** (if the user has env vars set): run the user's main entry-point with a one-line dummy prompt. Confirm the process exits 0 with no OTEL warnings (`No tracer provider has been initialized`, `Span context lost`), and that HoneyHive returns at least one new session at `<HH_API_URL>/sessions` (e.g. `https://api.dp1.us.honeyhive.ai/sessions` for the multi-tenant default).
2. **Grade the trace.** Run the bundled helper to fetch the session's events and surface the mechanical numbers (event counts by type, deepest LLM nesting, protocol-attribute coverage):

   ```bash
   ./trace-check.sh <session-id>
   ```

   Then open the new session in the UI and grade against [success.md](success.md) — trace structure, clean inputs/outputs, visible semantic failures, end-to-end summarisability. **A mechanically-correct integration that produces a messy trace is not done.** If the trace is messy (deeply hidden LLM calls, wrong nesting, missing tool linkage, missing user-query identifiability), circle back to the language reference and adjust strategy / session-boundary placement / event payload shape.
3. **Doc-gap surfacing.** If during discovery you found a framework, instrumentor, or OTel exporter combination that isn't covered above, do **not** improvise. Tell the user: "I've flagged this as a doc gap; here's the working install I produced; please open an issue at <https://github.com/honeyhiveai/skills/issues> if you'd like first-class coverage."

## Phase 3 — Stop

Single-pass. Do not continue iterating after success criteria are met. Instrumentation is the only goal — once spans are flowing and the trace grades well, hand off to the user. Anything beyond instrumentation (evaluating quality, improving prompts, tuning retrieval) is out of scope for this skill.

## References

Load only when the phase calls for them. Validation references and the language setup are the **primary** ones — Phase 0 always loads both validation refs, Phase 1 always loads exactly one setup ref. The rest are operational, loaded when a specific situation requires them.

**Peer files (top-level, loaded by phase):**

- [success.md](success.md) — qualitative rubric for grading the trace produced by Phase 2's smoke run. Trace structure, input/output cleanliness, semantic failure visibility, session summarisability. Phase 2 step 2 always loads this.
- [preflight.sh](preflight.sh) — Phase 0 helper. Validates `HH_API_URL` + `HH_API_KEY` and runs an authenticated `honeyhive events search` probe. Optional `HH_PROJECT` check. Use when the `honeyhive` CLI is available; otherwise fall back to the curl in [`references/network-validation.md`](references/network-validation.md).
- [trace-check.sh](trace-check.sh) — Phase 2 helper. Takes a `<session-id>` and prints mechanical counts (events by type, deepest LLM nesting, protocol-attribute coverage) for the agent to grade against `success.md`. Mechanical PASS/FAIL exit codes; qualitative grading is the agent's call.

**Phase 0 — Validation:**

- [references/network-validation.md](references/network-validation.md) — `HH_API_KEY` + `HH_API_URL` sourcing, curl reachability check, status-code interpretation, TLS chain (self-host).
- [references/runtime-validation.md](references/runtime-validation.md) — sub-tree identification, language + runtime detection, framework + instrumentor-family detection, existing HoneyHive wiring, existing global `TracerProvider`. Output feeds Phase 1.

**Phase 1 — Setup (one of):**

- [references/python-setup.md](references/python-setup.md) — Python: dependency plan, native-OTel-vs-instrumentor branching, `tracer.create_session` placement, distributed propagation, GUID shortcut, verification.
- [references/ts-setup.md](references/ts-setup.md) — TypeScript: dependency plan, structured-logger wrapper around `@honeyhive/api-client`, session boundary placement, semconv-shaped event payloads, verification.
- [references/otel-setup.md](references/otel-setup.md) — Native OTel (any language): dependency / coexistence plan, early init, session-boundary baggage / span-processor pattern, span capture, distributed propagation, full `honeyhive.*` attribute table, verification.

**Operational (load when relevant):**

- [references/co-existence.md](references/co-existence.md) — sharing a `TracerProvider` with a non-HoneyHive vendor (Datadog, New Relic). Loaded from runtime-validation when an existing real provider is detected, and from setup files when dual-export is requested.
- [references/dedicated-deployments.md](references/dedicated-deployments.md) — operational details for dedicated and self-host wiring (per-path `server_url` / `serverUrl` / `baseUrl` parameters, hostname conventions). Loaded from network-validation when the deployment is non-default.
- [references/prod-gotchas.md](references/prod-gotchas.md) — production checklist (deps, threading, distributed tracing, memory caps, blocking calls, graceful exit, network policy, certs, PII, sampling).

## Hard rules (MUSTs)

- **Never proceed past Phase 0 without successful network validation.** Wrong URL or rejected key means every later step rebuilds sand. See [references/network-validation.md](references/network-validation.md).
- **Never globally register HoneyHive as the source-of-truth `TracerProvider`** (`trace.set_tracer_provider(hh.provider)`). The SDK doesn't do this; instrumentation code shouldn't either. See [references/co-existence.md](references/co-existence.md).
- **Never construct two tracers (Python) or two `Client` instances (TS).** Reuse the existing instance — runtime validation flags pre-existing wiring for this reason.
- **Never hardcode API keys.** Always sourced from env vars; literal keys in code are a Phase 0 refusal.
- **Never let `HH_API_URL` / `server_url` / `serverUrl` silently fall back to the wrong host** — confirm the deployment URL explicitly with the user (multi-tenant default is `https://api.dp1.us.honeyhive.ai`; dedicated and self-host customers have their own); see [references/dedicated-deployments.md](references/dedicated-deployments.md).
- **Never switch instrumentor families** (OpenInference ↔ Traceloop) without the user's explicit consent — they emit different attribute sets and switching breaks existing dashboards. (Python only; TS uses manual events, no instrumentor families.)
- **Never thread `session_id` / `event_id` through the user's existing function signatures** (TS, Phase 1) — use a module-level helper or async-context store instead.
- **Never bump SDK or framework versions** to make instrumentation work. If a version is incompatible, surface it; do not upgrade unilaterally.
- **Never modify test files or lock files** unless the user explicitly asks.
- **Never run a production deploy step.** Local smoke run is the verification ceiling; production rollout is a human decision.
