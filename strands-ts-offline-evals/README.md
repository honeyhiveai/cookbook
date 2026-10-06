# Strands TypeScript × HoneyHive offline evals

Run an offline experiment on a [Strands Agents](https://strandsagents.com/) TypeScript agent and see the results in HoneyHive. This cookbook runs a support agent against a small dataset, scores each answer, and records the whole run as a HoneyHive experiment.

You don't need a HoneyHive tracer SDK for this. It uses two standard pieces:

- **Tracing**: Strands emits OpenTelemetry spans natively. A standard OTLP exporter sends them to HoneyHive.
- **Experiment orchestration**: [`@honeyhive/api-client`](https://docs.honeyhive.ai/v2/sdk-reference/typescript) creates the run, records one session per datapoint, writes evaluator scores, and closes the run.

## What you get in HoneyHive

One experiment run in **Experiments** with:

- one session per datapoint, each with the full agent trace: the `invoke_agent` span, one span per reasoning cycle, and the model and tool calls inside each cycle
- the agent's answer as the session output, and the reference answer as `feedback.ground_truth`
- two scores per session: `correctness` (an LLM judge that compares the answer with the reference) and `concise` (a deterministic check)
- aggregate scores for the run, which you can compare against other runs

## How it works

```
for each datapoint:
  1. sessions.create   → a session with run_id, dataset_id, datapoint_id in metadata
  2. agent.invoke      → Strands spans go to HoneyHive over OTLP, tagged with the session ID
  3. evaluators        → your TypeScript functions score the output
  4. events.update     → outputs, ground truth, and scores go on the session
experiments.createRun before the loop, experiments.updateRun (status: completed) after it
```

This links runs, sessions, and datapoints the same way as the HoneyHive Python SDK's `evaluate()`. One difference: this cookbook puts evaluator scores on the session event, and `evaluate()` puts them on the function's span.

| File | What it does |
| --- | --- |
| `src/tracing.ts` | Registers an OTLP exporter for Strands spans. Includes a span processor that copies `honeyhive.session_id` from the root agent span to its child spans, so every span lands in the datapoint's session. |
| `src/agent.ts` | The agent under test: a support agent with `get_product` and `calculator` tools. Replace it with your own agent. |
| `src/dataset.ts` | An inline dataset, plus a loader for datasets stored in HoneyHive. |
| `src/evaluators.ts` | The evaluator functions. An evaluator gets the datapoint and the agent's output, and returns a number or a boolean. |
| `src/experiment.ts` | `runExperiment()`, the orchestration loop. It does not depend on Strands, so you can reuse it with any agent. |
| `src/index.ts` | Connects the pieces and prints a link to the run in HoneyHive. |

## Prerequisites

| Requirement | Where to get it |
| --- | --- |
| Node.js 22+ | [nodejs.org](https://nodejs.org). The Strands TypeScript SDK requires Node.js 22. |
| pnpm | [pnpm.io/installation](https://pnpm.io/installation) |
| HoneyHive project API key (`hh_...`) | In HoneyHive, **Settings > Project > API Keys**, **Project** tab. The experiments API uses a project key. |
| OpenAI API key | [platform.openai.com/api-keys](https://platform.openai.com/api-keys). Used by the agent and the LLM judge. |

## Setup

```bash
cd strands-ts-offline-evals
pnpm install
cp .env.example .env
```

Fill in `.env`:

```bash
HH_PROJECT_API_KEY=your_honeyhive_api_key
OPENAI_API_KEY=your_openai_api_key
```

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `HH_PROJECT_API_KEY` | Yes | | HoneyHive project API key. Used for the OTLP export and for the experiments API. |
| `OPENAI_API_KEY` | Yes | | Key for the agent's model and for the LLM judge. |
| `HH_DATA_PLANE_URL` | No | `https://api.dp1.us.honeyhive.ai` | HoneyHive API host. Change it for dedicated or self-hosted deployments. |
| `HH_APP_URL` | No | `https://app.us.honeyhive.ai` | HoneyHive app URL for the printed run link. Change it for dedicated or self-hosted deployments. |
| `HH_DATASET_ID` | No | | Run against a HoneyHive dataset instead of the inline dataset. Each datapoint needs `inputs.question` and `ground_truth.answer`. |

## Run

```bash
pnpm start
```

The script prints a summary line, a link to the run, and the session IDs:

```
Ran 3 datapoints, 0 failed.
Results: https://app.us.honeyhive.ai/p/<project-id>/experiments/runs/<run-id>
Session IDs: <session-id> <session-id> <session-id>
```

Open the link to see each datapoint's scores, and select a row to see that datapoint's trace. To score the same sessions with Strands Evals evaluators, pass the session IDs to [strands-evals-honeyhive](../strands-evals-honeyhive).

To check types without running the experiment:

```bash
pnpm typecheck
```

## Use your own agent

1. Replace `createSupportAgent()` in `src/agent.ts` with your agent. Keep `traceAttributes: { 'honeyhive.session_id': sessionId }`. Without it, the agent's spans don't join the datapoint's session.
2. Change the `task` function in `src/index.ts` so it maps a datapoint's `inputs` to your agent's input and returns the output as a string.
3. Replace the evaluators in `src/evaluators.ts`, or add new ones to the `evaluators` object in `src/index.ts`. The object key becomes the metric name in HoneyHive.

To use a different model provider, replace `OpenAIModel` with another Strands model class, such as `BedrockModel` from `@strands-agents/sdk/models/bedrock`, and install that provider's client package.

## Troubleshooting

**Each span appears in its own session.** The agent is missing `traceAttributes: { 'honeyhive.session_id': sessionId }`, or `src/tracing.ts` is not registered. `setupTracing()` must run before the first agent call.

**The run page shows no scores right after the run.** Refresh the page after a short wait. To read the results in code, call `client.experiments.getSummary({ run_id })`.

**A datapoint failed.** The session keeps the error in `metadata.error` and has no scores, and the run's `metadata.failed_datapoints` counts it. If an evaluator throws, the other evaluators still score that datapoint. If anything else throws, the run is marked `failed`.

**Spans are missing from a session.** The process exited before the exporter flushed. `runExperiment()` calls `flush()` before it closes the run, and `index.ts` calls `provider.shutdown()` at the end. Keep both if you change the entry point.

## Learn more

- [Trace Strands Agents with HoneyHive](https://docs.honeyhive.ai/v2/integrations/strands)
- [TypeScript API SDK reference](https://docs.honeyhive.ai/v2/sdk-reference/typescript)
- [Strands Agents TypeScript SDK on npm](https://www.npmjs.com/package/@strands-agents/sdk)
