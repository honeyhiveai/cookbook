# Cursor SDK × HoneyHive

Trace [Cursor SDK](https://cursor.com/docs/sdk/typescript) agent runs in [HoneyHive](https://honeyhive.ai). This cookbook hooks Cursor's `onStep` callback and exports each run as a HoneyHive trace using the `[@honeyhive/api-client](https://www.npmjs.com/package/@honeyhive/api-client)`.

One Cursor run becomes a HoneyHive session containing:

- a top-level `session.start` event
- an `agent.run` chain event with the prompt, result, model, Git metadata, and step counts
- one `tool.<name>` event per Cursor tool call, with args, result, and execution time
- a final `turn.agent` event with the assistant's response

The instrumentor redacts common secret fields, truncates large payloads, and stores only the workspace folder name instead of the full local path.

## Prerequisites


| Requirement       | Where to get it                                                                      |
| ----------------- | ------------------------------------------------------------------------------------ |
| Node.js 20+       | [nodejs.org](https://nodejs.org)                                                     |
| pnpm              | [pnpm.io/installation](https://pnpm.io/installation)                                 |
| Cursor API key    | [Cursor Dashboard → Integrations](https://cursor.com/dashboard/integrations)         |
| HoneyHive API key | [HoneyHive Dashboard](https://app.honeyhive.ai) (or [sign up](https://honeyhive.ai)) |


## Setup

```bash
cd cursor-sdk-honeyhive
pnpm install
cp .env.example .env
```

Fill in `.env`:

```bash
CURSOR_API_KEY=your_cursor_api_key
HH_API_KEY=your_honeyhive_api_key
```

### Environment variables


| Variable               | Required | Default                     | Description                                                           |
| ---------------------- | -------- | --------------------------- | --------------------------------------------------------------------- |
| `CURSOR_API_KEY`       | Yes      | –                           | Cursor user or service account API key                                |
| `HH_API_KEY`           | Yes      | –                           | HoneyHive API key                                                     |
| `HH_PROJECT`           | No       | `Cursor SDK HoneyHive Demo` | Project label written to event metadata                               |
| `HH_SOURCE`            | No       | `cursor-sdk-honeyhive`      | `source` field on every exported event                                |
| `HH_API_URL`           | No       | `https://api.honeyhive.ai`  | HoneyHive API endpoint (set for self-hosted or dedicated deployments) |
| `CURSOR_MODEL`         | No       | `composer-2`                | Cursor model id passed to `Agent.create`                              |
| `CURSOR_PROMPT`        | No       | *summarize this README*     | Prompt sent to the agent                                              |
| `CURSOR_WORKSPACE_DIR` | No       | `process.cwd()`             | Working directory for the local Cursor agent                          |


## Run

```bash
pnpm start
```

The default prompt asks Cursor to read `README.md` and summarize this example without modifying files. Once the run finishes, open the [HoneyHive Log Store](https://docs.honeyhive.ai/v2/tracing/ui-flows) to view the trace.

## Trace shape

Each Cursor run produces one HoneyHive session with the following events:


| Event           | Type    | Notes                                                                                                                                                                                           |
| --------------- | ------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `session.start` | session | Top-level container with prompt, workspace, status, and the SDK tag (`sdk: cursor`).                                                                                                            |
| `agent.run`     | chain   | Cursor SDK invocation. Inputs: prompt + workspace. Outputs: status, result, accumulated thinking. Metadata includes `cursor.agent_id`, `cursor.run_id`, `cursor.git`, and `cursor.step_counts`. |
| `tool.<name>`   | tool    | One per Cursor [tool call](https://cursor.com/docs/sdk/typescript) (`shell`, `edit`, `read`, `write`, `grep`, `mcp`, etc.). Captures args, result, status, and execution time.                  |
| `turn.agent`    | model   | Final model turn — prompt + response text, tagged with `gen_ai.system: cursor`.                                                                                                                 |


Tool, agent, and model events use [GenAI semantic attributes](https://opentelemetry.io/docs/specs/semconv/gen-ai/) (`gen_ai.system`, `gen_ai.operation.name`, `gen_ai.tool.name`) so they line up with HoneyHive's standard views.

## How it works

The reusable code lives in `[instrumentor/](./instrumentor)` and is exported from `[instrumentor/index.ts](./instrumentor/index.ts)`:

```typescript
import { HoneyHiveCursorInstrumentor } from './instrumentor/index.js';

const instrumentor = new HoneyHiveCursorInstrumentor({
  apiKey: process.env.HH_API_KEY,
  project: 'My Cursor Project',
});

const result = await instrumentor.traceRun({
  agent,
  message: 'Run the test suite and fix any failing tests',
});
```

`traceRun` subscribes to the Cursor SDK `[onStep` callback]([https://cursor.com/docs/sdk/typescript](https://cursor.com/docs/sdk/typescript)), buffers tool calls, awaits `run.wait()`, then exports the full trace through `@honeyhive/api-client`'s `sessions.start` and `sessions.addTraces` APIs.

### Customizing what gets sent

Pass a `sanitize` function to scrub or rewrite anything before it leaves your process:

```typescript
const instrumentor = new HoneyHiveCursorInstrumentor({
  apiKey: process.env.HH_API_KEY,
  sanitize: (value, context) => {
    if (context === 'toolArgs') {
      return scrubPii(value);
    }
    return value;
  },
});
```

Sanitize contexts: `prompt`, `result`, `thinking`, `toolArgs`, `toolResult`, `metadata`, `workspace`. The default sanitizer redacts keys matching `api[_-]?key|authorization|cookie|credential|password|secret|token` and truncates strings over 4 KB.

## Adapting this example

This directory is shaped like a future package entrypoint, while `[index.ts](./index.ts)` stays the runnable cookbook. Common extensions:

- Swap `local: { cwd }` for a Cursor [cloud runtime](https://cursor.com/docs/sdk/typescript) to trace cloud agent runs the same way.
- Wrap a long-running script that calls `agent.send()` multiple times, reusing one `traceRun` per prompt.
- Pipe additional metadata (PR number, CI run id, user id) by extending `traceRun` with extra `metadata` fields on the events.

## Development

Type-check and build the instrumentor as a standalone package:

```bash
pnpm typecheck
pnpm build
```

## Links

- [Cursor TypeScript SDK docs](https://cursor.com/docs/sdk/typescript)
- [Cursor APIs overview](https://cursor.com/docs/api)
- `[@cursor/sdk` on npm]([https://www.npmjs.com/package/@cursor/sdk](https://www.npmjs.com/package/@cursor/sdk))
- [HoneyHive docs (v2)](https://docs.honeyhive.ai/v2/introduction/tracing-quickstart)
- `[@honeyhive/api-client` on npm]([https://www.npmjs.com/package/@honeyhive/api-client](https://www.npmjs.com/package/@honeyhive/api-client))
- [More HoneyHive cookbooks](../README.md)

