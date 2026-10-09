# Strands TypeScript × HoneyHive offline evals

Run an offline experiment on a [Strands Agents](https://strandsagents.com/) TypeScript agent and see the results in HoneyHive. The cookbook runs a support agent against a small dataset, scores each answer, and records the run as a HoneyHive experiment.

It uses two standard pieces:

- **Tracing:** Strands emits OpenTelemetry spans, and an OTLP exporter sends them to HoneyHive.
- **Experiment:** [`@honeyhive/api-client`](https://docs.honeyhive.ai/v2/sdk-reference/typescript) creates the run, one session per datapoint, and the scores.

| File | What it does |
| --- | --- |
| `src/tracing.ts` | Sends Strands spans to HoneyHive. A span processor copies `honeyhive.session_id` from the agent span to its child spans, so each datapoint's spans land in one session. |
| `src/experiment.ts` | The agent, the dataset, two evaluators, and the experiment loop, in that order. |

The experiment makes these API calls:

```
experiments.createRun                      → one run for the dataset
for each datapoint:
  sessions.create                          → a session linked to the run and the datapoint
  run the agent                            → its spans join the session
  events.update                            → the answer, the reference answer, and the scores
experiments.updateRun (status: completed)  → close the run
```

## Prerequisites

| Requirement | Where to get it |
| --- | --- |
| Node.js 22+ | [nodejs.org](https://nodejs.org). The Strands TypeScript SDK requires Node.js 22. |
| pnpm | [pnpm.io/installation](https://pnpm.io/installation) |
| HoneyHive project API key (`hh_...`) | In HoneyHive, **Settings > Project > API Keys**, **Project** tab. |
| OpenAI API key | [platform.openai.com/api-keys](https://platform.openai.com/api-keys). Used by the agent and the LLM judge. |

## Run

```bash
cd strands-ts-offline-evals
pnpm install
cp .env.example .env   # then fill in HH_PROJECT_API_KEY and OPENAI_API_KEY
pnpm start
```

The script prints a link to the run:

```
Results: https://app.us.honeyhive.ai/p/<project-id>/experiments/runs/<run-id>
```

Open it to see each datapoint's `correctness` and `concise` scores and the run averages. Select a row to see that datapoint's trace.

For dedicated or self-hosted deployments, set `HH_DATA_PLANE_URL` and `HH_APP_URL` in `.env`.

## Use your own agent

In `src/experiment.ts`:

1. Replace `runAgent()` with your agent. Keep `traceAttributes: { 'honeyhive.session_id': sessionId }`, which puts the agent's spans in the datapoint's session.
2. Replace `dataset` with your test cases.
3. Replace the evaluators. Each key in `metrics` becomes a metric name in HoneyHive.

To use another model provider, replace `OpenAIModel` with another Strands model class, such as `BedrockModel` from `@strands-agents/sdk/models/bedrock`.

## Learn more

- [Trace Strands Agents with HoneyHive](https://docs.honeyhive.ai/v2/integrations/strands)
- [TypeScript API SDK reference](https://docs.honeyhive.ai/v2/sdk-reference/typescript)
