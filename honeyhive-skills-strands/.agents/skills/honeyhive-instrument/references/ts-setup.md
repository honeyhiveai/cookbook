# TypeScript setup

For Node / Bun / Deno apps using `@honeyhive/api-client` (the manual session+event API).

Assumes [`network-validation.md`](network-validation.md) has confirmed reachability and [`runtime-validation.md`](runtime-validation.md) has produced findings (`framework`, `existing_hh_wiring`, `existing_otel_provider`, `runtime_version`). This file consumes those findings rather than re-detecting.

> **Mental model: TS instrumentation should feel like the user added a structured logger.** A small, module-level wrapper that's easy to import from any route or service, takes the relevant correlation GUID at session start, and structures its event payloads around OpenTelemetry gen_ai semconv so existing dashboards and the success-criteria rubric grade well without per-call thinking.

There is no first-party TS auto-instrumentor today. The skill's job is to author the wrapper for the user (or adapt their existing logger surface) and place its calls correctly across the request lifecycle.

## Step 0 — Translate runtime-validation findings into a setup plan

Inputs (from [`runtime-validation.md`](runtime-validation.md) output):

- `runtime_version` (Node 18 / 20 / 22, Bun, Deno)
- `framework` (the LLM SDK pinned in `package.json` — `openai`, `@anthropic-ai/sdk`, `@langchain/*`, etc.)
- `existing_hh_wiring` (file:line, or `none`)
- `existing_otel_provider` (`none` / `proxy-noop` / `real:<vendor>` / `real:custom-mutating`)

Decisions:

| Finding | Action |
|---|---|
| `existing_hh_wiring != none` | **Reuse the existing `Client` instance.** Don't construct a second one. Place the logger wrapper around the existing client; the rest of setup adds `startSession` / `event` calls. |
| `@honeyhive/api-client` missing from `package.json` | Install explicitly (`pnpm add @honeyhive/api-client` / `npm i @honeyhive/api-client`). Do not silently mutate a manifest the user did not commit. |
| `runtime_version < node-18` | Surface as a finding. `AsyncLocalStorage` works from Node 16+ but `crypto.randomUUID()` and several runtime APIs the wrapper relies on need Node 18+. Recommend an upgrade rather than working around. |
| Bun / Deno | Both support `AsyncLocalStorage` (via Node compatibility) — the wrapper pattern works as-is. Confirm `process.env` is the env-var source the user's runtime uses (vs `Deno.env`). |
| `existing_otel_provider = real:<vendor>` | Inform the user that the TS path runs through `@honeyhive/api-client` (manual events) rather than OTel, so HoneyHive doesn't share a TracerProvider with their other vendor. Both pipelines coexist trivially. |

**Never bump framework versions** to make instrumentation work; surface the incompatibility instead.

## Step 1 — Author the logger wrapper (once, module-level)

A single `Client` instance from `@honeyhive/api-client`, instantiated at module load with `apiKey` + `project` from `process.env`. Wrap it in a small helper exposing a logger-shaped surface:

```ts
// trace.ts (or src/instrumentation/trace.ts)
import { Client } from "@honeyhive/api-client";
import { AsyncLocalStorage } from "node:async_hooks";

const client = new Client({
  apiKey: process.env.HH_API_KEY!,
  baseUrl: process.env.HH_API_URL,            // dedicated/self-host: set explicitly
});

const sessionContext = new AsyncLocalStorage<{ sessionId: string }>();

export const logger = {
  startSession: async (guid: string, name: string, inputs?: unknown) => { /* ... */ },
  event: async (eventName: string, payload: SemconvEventPayload) => { /* reads sessionId from sessionContext */ },
  withSession: async <T>(guid: string, name: string, fn: () => Promise<T>) => { /* runs fn inside sessionContext.run */ },
};
```

Three properties make this feel like a logger and not an SDK:

1. **Module-level singleton.** Imported wherever needed (`import { logger } from "./trace"`); no per-route construction.
2. **Async-context-aware.** `AsyncLocalStorage` (or equivalent) carries the active session id across `await` boundaries so handlers downstream of a route don't need to receive `sessionId` as a function argument.
3. **Semconv-shaped event payloads** (see Step 3) so the call site reads like structured logging, not OTel SDK ceremony.

## Step 2 — Place `startSession` at the request/job boundary; events at each model call

Same idea as Python's `tracer.create_session`: open a session per logical unit of work.

| App shape | Where to call `logger.startSession` (or `withSession`) |
|---|---|
| **Express / Koa / Hapi** | Route-scoped middleware that wraps the handler in `logger.withSession(guid, name, () => next())`. |
| **Next.js / Remix** | At the top of each route handler / `loader` / `action`. |
| **Fastify** | A `preHandler` hook that runs `withSession`. |
| **Cloudflare Workers / Vercel Edge** | At the top of `fetch(request)`. |
| **AWS Lambda** | At the top of the handler — and `await` everything before returning so spans flush before SIGKILL. (See [`prod-gotchas.md`](prod-gotchas.md) §6.) |
| **BullMQ / RabbitMQ / SQS workers** | At the start of each `process(job)` callback. |
| **Long-lived chat session** | When the conversation starts; cache the session id in the conversation state so follow-up turns reuse it. |

The GUID passed to `startSession` should come from whatever correlation id the user's app already propagates (`X-Request-Id`, conversation id, job id). If the GUID isn't UUID-shaped, convert deterministically (`uuidv5(NAMESPACE_URL, rawGuid)`) so the same input always becomes the same session id — same trick as Python's GUID shortcut. Avoids needing to set up baggage / W3C tracecontext propagators.

If the user has no propagated GUID, the wrapper should default to `crypto.randomUUID()`.

## Step 3 — Structure event payloads around gen_ai semconv

The wrapper's `event(name, payload)` shape is a thin translation to `client.events.createEvent`. Make the payload shape **mirror OpenTelemetry gen_ai semantic conventions** so semconv-keyed dashboards and the [`success.md`](../success.md) rubric (clean inputs/outputs on core events, full message history visible) grade well by default:

```ts
await logger.event("openai.chat.completions", {
  gen_ai: {
    system: "openai",
    request: {
      model: "gpt-4o-mini",
      temperature: 0.2,
      max_tokens: 1024,
    },
    usage: {
      input_tokens: response.usage.prompt_tokens,
      output_tokens: response.usage.completion_tokens,
    },
    response: { model: response.model, id: response.id },
  },
  inputs: { messages, tools },          // full message history + tool list
  outputs: { content, tool_calls },     // full response payload
  metadata: { request_path: req.path },
});
```

The wrapper flattens `gen_ai.*` into the event metadata HoneyHive stores so semconv-keyed views and any third-party `gen_ai`-aware tools work without separate shaping.

For tool calls and agent steps, follow the same shape with appropriate `event_type` (`"tool"`, `"chain"`, `"model"`):

```ts
await logger.event("calculator.evaluate", { inputs: { expression }, outputs: { result }, event_type: "tool" });
```

## Step 4 — Verify

Before declaring success, confirm:

- Exactly **one** `Client` from `@honeyhive/api-client` instantiated at module load.
- `apiKey` from `process.env.HH_API_KEY`, never a literal. For dedicated/self-host, `baseUrl` from `process.env.HH_API_URL` per [`dedicated-deployments.md`](dedicated-deployments.md).
- `logger.startSession(...)` (or `withSession`) is invoked at every session boundary in Step 2's table — the skill should be able to point at the exact files/lines.
- `logger.event(...)` is called for every LLM call, tool call, and meaningful agent step — payloads structured per Step 3.
- Async-context store (`AsyncLocalStorage` or framework-equivalent) propagates the session id across `await` boundaries; no `sessionId` argument has been threaded through user functions.
- The logger import works cleanly from every route/service in the relevant subtree; the skill should be able to grep for `import { logger }` and confirm coverage.
- Run a smoke test on one route with a real LLM call. Inspect the trace against [`success.md`](../success.md): is the user's original query identifiable? Do LLM events show full message history + tools + response? Are agent/tool nested under their parent agent event?

If the smoke trace shows orphan events, missing message history, or unclear input-output shapes — the wrapper is mechanically correct but the payload structure or session-boundary placement is wrong. Adjust before handing off.
