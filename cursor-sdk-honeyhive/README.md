# Cursor SDK HoneyHive Tracing Cookbook

Trace a Cursor SDK agent run in HoneyHive. This example uses the Cursor TypeScript SDK `onStep` callback and the public HoneyHive TypeScript client to turn one agent run into a HoneyHive trace with a session event, an agent event, tool events, and a final turn event.

## What This Shows

- Create a local Cursor SDK agent from TypeScript.
- Capture Cursor tool calls as HoneyHive trace events.
- Export the trace through `@honeyhive/api-client`.
- Print Cursor and HoneyHive IDs for the exported run.

## Prerequisites

- Node.js 20+
- pnpm
- A Cursor API key
- A HoneyHive API key

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

Optional settings:

- `HH_PROJECT` sets a project label in trace metadata.
- `HH_API_URL` points at a self-hosted or dedicated HoneyHive API endpoint.
- `CURSOR_MODEL` defaults to `composer-2`.

## Run

```bash
pnpm start
```

The default prompt asks Cursor to read this README and summarize the example without modifying files. After the run finishes, the script exports spans to HoneyHive and prints metadata like:

```json
{
  "cursorAgentId": "agent-id",
  "cursorRunId": "run-id",
  "cursorStatus": "finished",
  "honeyhiveSessionId": "session-id",
  "honeyhiveEventId": "event-id"
}
```

## Trace Shape

The exported trace uses HoneyHive event metadata and GenAI semantic attributes. By default, the instrumentor redacts common secret fields, truncates large payloads, and stores only the workspace folder name instead of the full local path.

- `session.start`: top-level HoneyHive session event.
- `agent.run`: Cursor SDK agent invocation with prompt, result, model, Git metadata, and step counts.
- `tool.<name>`: one event per Cursor SDK tool call observed through `onStep`.
- `turn.agent`: final model turn with prompt and response text.

## Adapting This Example

Use this cookbook as a starting point for tracing longer Cursor SDK workflows. The reusable code lives in `instrumentor/` and is exported from `instrumentor/index.ts`:

```typescript
import { HoneyHiveCursorInstrumentor } from './instrumentor/index.js';
```

This directory is intentionally shaped like a future package entrypoint, while `index.ts` remains the runnable cookbook example. To customize what gets sent to HoneyHive, pass a `sanitize` function to `HoneyHiveCursorInstrumentor`.

To verify the package entrypoint locally:

```bash
pnpm build
```

