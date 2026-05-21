# Runtime validation (Phase 0)

Once [`network-validation.md`](network-validation.md) confirms the user's credentials reach HoneyHive, the next step is to inspect the user's runtime: which language, which framework, what's already wired up, what existing tracing infrastructure exists. **Runtime validation feeds directly into Phase 1 setup** — the language-specific setup file consumes the structured findings produced here rather than re-detecting from scratch.

## Step 0 — Identify the right sub-tree

In a monorepo, the LLM/agent app may live in a subfolder (`packages/agent`, `services/rag`, `apps/chatbot`). Locate the entry-point file the user is referring to. If ambiguous, ask. **All subsequent reads in runtime validation, and all edits in Phase 1 setup, are scoped to this subtree.**

Cheap way to scan for candidates:

```bash
# Files that import an LLM SDK — likely entry-points.
rg -l 'openai|anthropic|langchain|llama_index|dspy|crewai|@anthropic-ai/sdk|honeyhive' \
  --type-add 'web:*.{py,ts,tsx,js,mjs,go,rs,java,cs}' --type web \
  | head -20
```

Confirm the scope with the user before proceeding.

## Step 1 — Detect language + runtime

Look at the manifest files in the chosen subtree to identify the language and runtime:

| Language | Manifest signals |
|---|---|
| **Python** | `pyproject.toml`, `requirements.txt`, `uv.lock`, `Pipfile.lock`, `setup.py` |
| **Node / Bun / Deno** | `package.json`, `pnpm-lock.yaml`, `yarn.lock`, `bun.lockb`, `deno.json` |
| **Go** | `go.mod`, `go.sum` |
| **Rust** | `Cargo.toml`, `Cargo.lock` |
| **Java / JVM** | `pom.xml`, `build.gradle`, `build.gradle.kts` |
| **.NET** | `*.csproj`, `*.fsproj`, `packages.lock.json` |

The detected language determines which Phase 1 setup file to load:

- Python → [`python-setup.md`](python-setup.md)
- Node/Bun/Deno → [`ts-setup.md`](ts-setup.md)
- Anything else → [`otel-setup.md`](otel-setup.md)

Also note the **runtime version** (Python 3.x, Node 18 / 20 / 22, Go 1.x, etc.) — some downstream concerns (Lambda flush, async-context support) depend on it.

## Step 2 — Detect framework + instrumentor family (Python especially)

For each detected language, look at the dependency manifest to identify the LLM/agent framework and any pinned instrumentor:

**Python — frameworks:**

```bash
# In the subtree's pyproject.toml / requirements.txt:
rg '^(openai|anthropic|langchain|langgraph|llama-index|dspy|crewai|autogen|semantic-kernel|strands|openai-agents|anthropic-ai/claude-agent-sdk|google-adk|pydantic-ai|litellm)\b'
```

**Python — instrumentor family** (decisive for Path A vs Path B in setup):

```bash
rg '^openinference-instrumentation-' deps_files...    # OpenInference family
rg '^opentelemetry-instrumentation-' deps_files...    # OpenLLMetry/Traceloop family
```

**Critical:** if both families are pinned, do **not** silently pick one — surface the conflict and ask. If exactly one is pinned, that's the family for setup; never switch.

**TypeScript — frameworks:**

```bash
rg '"(openai|@anthropic-ai/sdk|@langchain/.+|@llamaindex/.+|crewai-js)"' package.json
```

There is no first-party TS auto-instrumentor today — TS uses `@honeyhive/api-client` for manual session/event construction.

**Other languages:** look for `opentelemetry-*` or vendor-OTel SDKs (`go.opentelemetry.io/otel`, `Microsoft.OpenTelemetry`, etc.) — the language is going through Path C (native OTel) regardless of framework.

## Step 3 — Check for pre-existing HoneyHive wiring

Search the subtree for existing HoneyHive instantiations. **If a tracer / client already exists, never construct a second one.** Reuse the existing instance.

```bash
# Python:
rg 'HoneyHiveTracer\.init\b|from honeyhive import' --type py

# TypeScript / JS:
rg 'new Client\b.*api-client|from .@honeyhive/api-client.|HoneyHiveTracer\.init\b' \
  --type ts --type js
```

Findings to record:

- **No wiring found** → Phase 1 setup creates the wiring fresh.
- **Existing wiring found** → Phase 1 setup augments it (places `tracer.create_session` calls at session boundaries; doesn't re-init the tracer). Capture file:line so the setup file knows where to read from.
- **Multiple `HoneyHiveTracer.init` / `new Client()` calls** — bug. Surface to the user; they need to consolidate before instrumentation can proceed cleanly.

## Step 4 — Check for a pre-existing global OTel `TracerProvider`

Look for code that has already configured a global OTel `TracerProvider` for a non-HoneyHive vendor (Datadog, New Relic, vendor-native). HoneyHive's tracer init is independent and won't hijack the global, so this isn't a refusal case — but it informs the dual-export decision in Phase 1.

```bash
# Python:
rg 'trace\.set_tracer_provider\(|TracerProvider\(' --type py

# TypeScript / JS:
rg '(trace|api)\.setTracerProvider\(|new (Node|Web)TracerProvider\b' --type ts --type js

# Go:
rg 'otel\.SetTracerProvider\(|sdktrace\.NewTracerProvider\(' --type go
```

Findings to record:

- **None / proxy-noop only** → no co-existence concern. (See [`co-existence.md`](co-existence.md) §0 for the proxy/no-op detection signals — class name contains `Proxy`/`NoOp`/`Default`, no SpanProcessor attached, no exporter configured.)
- **Real provider, exporter pointing at Datadog/New Relic/etc.** → flag for Phase 1: ask the user whether they want dual-export. Decision tree in [`co-existence.md`](co-existence.md).
- **Real provider with a custom mutating SpanProcessor** → flag for Phase 1 to refuse dual-export (mutating processors will rewrite gen_ai/openinference attributes).

## Output to Phase 1 setup

Phase 1 setup files (`python-setup.md` / `ts-setup.md` / `otel-setup.md`) consume the following findings:

```
subtree                = <path>
language               = python | typescript | go | rust | java | dotnet | other
runtime_version        = <e.g. python-3.11 / node-20 / go-1.22>
framework              = <e.g. openai / langchain / dspy / crewai / native>
framework_version      = <pinned version>
instrumentor_family    = openinference | traceloop | none | conflict
existing_hh_wiring     = <list of file:line> | none
existing_otel_provider = none | proxy-noop | real:<vendor> | real:custom-mutating
existing_provider_ref  = <file:line if real>
deployment             = multi-tenant | dedicated | self-host    (from network-validation)
```

The Phase 1 setup file branches off these values rather than re-running detection. Surface any conflicts (multiple instrumentor families, multiple existing tracers, custom-mutating provider) before any setup work begins.

## When in doubt — ask, don't infer

If any field above can't be determined with high confidence (the subtree has no manifest, the framework imports are dynamic, two instrumentor families are pinned, the existing-tracer call is wrapped in a factory function), surface the ambiguity to the user. Inferring a wrong framework or family produces a working-looking install that silently emits the wrong attribute set — exactly the kind of failure the validation phase exists to prevent.
