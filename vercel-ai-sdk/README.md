# Vercel AI SDK + HoneyHive

A minimal Node.js example showing how to add HoneyHive tracing to the [Vercel AI SDK](https://ai-sdk.dev/) (v6).

## What this demonstrates

- `generateText` with tool calling and multi-step execution
- `streamText` for an interactive multi-turn chat
- HoneyHive tracing via the `experimental_telemetry` option

## Prerequisites

- Node.js 18+
- An [OpenAI API key](https://platform.openai.com/api-keys)
- A [HoneyHive API key](https://app.honeyhive.ai)

## Setup

```bash
# Install dependencies
npm install

# Copy and fill in your API keys
cp .env.example .env
```

## Run

```bash
npm start
```

The script runs a single-turn `generateText` call first, then drops into an interactive chat. Type `exit` to quit.

## How it works

The only HoneyHive-specific code is:

1. **Initialize the tracer** at the top of your file:

```typescript
import { HoneyHiveTracer } from "honeyhive";

const tracer = await HoneyHiveTracer.init({
  apiKey: process.env.HH_API_KEY,
  project: process.env.HH_PROJECT,
  source: "dev",
  sessionName: "vercel-ai-sdk-demo",
});
```

2. **Pass the tracer** to any AI SDK function via `experimental_telemetry`:

```typescript
const result = await generateText({
  model: openai("gpt-4o-mini"),
  prompt: "Hello!",
  experimental_telemetry: {
    isEnabled: true,
    tracer: tracer.getTracer(), // <-- this line
  },
});
```

That's it. All `generateText`, `streamText`, `generateObject`, and `streamObject` calls with telemetry enabled will appear in your HoneyHive project.

## For Next.js apps

If you're using Next.js instead of plain Node.js, see the [Vercel AI SDK integration docs](https://docs.honeyhive.ai/integrations/vercel) for the environment-variable-based setup using `@vercel/otel`.
