# Drex with HoneyHive

[Drex](https://console.nace.ai/docs) is a decision-model API from Nace. It answers typed questions about a piece of state: yes/no (`Noul`), multiple choice (`Choice`) and a graded score (`Score`), each with probabilities. It serves the same `POST /v1/systemone` as TypeSafe's Jev, so the `typesafe-sdk` client and its OpenInference instrumentor work against it with a base URL, a key and an explicit model.

This cookbook has two examples:

- `trace_drex.py` traces a Drex call in HoneyHive, the same steps as the [TypeSafe tracing guide](https://docs.honeyhive.ai/v2/integrations/typesafe).
- `eval_drex.py` uses Drex as a judge in a HoneyHive experiment, as a client-side evaluator.

## Getting started

### Prerequisites

- Python 3.11+
- A HoneyHive project API key
- A Drex API key from [console.nace.ai](https://console.nace.ai), or the URL and key of your own Drex deployment

### Installation

```bash
git clone https://github.com/honeyhiveai/cookbook.git
cd cookbook/drex-honeyhive-cookbook
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

### Configuration

Copy `.env.example` to `.env` and fill it in, then export the variables:

```bash
HH_API_KEY=your-honeyhive-api-key
TYPESAFE_API_KEY=your-drex-api-key
TYPESAFE_BASE_URL=https://console.nace.ai
```

`TYPESAFE_BASE_URL` is the host without `/v1`. For Drex on your own infrastructure, use that deployment's URL.

## Trace a Drex call

```bash
python trace_drex.py
```

It asks three questions about a support ticket in one request and prints the answers. In HoneyHive, the session `drex-support-triage` holds a model event with the request, the typed answers, token usage and the resolved model name.

Things to know:

- Pass a Drex model id such as `drex-max`. The SDK's default, `jev-latest`, is not a Drex model and is refused.
- `HoneyHiveTracer.init()` logs `Unknown openinference.span.kind: DECISION, defaulting to tool`. It is harmless: the event is stored as a tool-type event.
- With `honeyhive` 1.8.1, leave `HH_INGESTION_API_KEY` unset when you only have a project key. The tracer falls back to `HH_API_KEY`, and rejects a project key placed in `HH_INGESTION_API_KEY`.

## Use Drex as a judge

```bash
python eval_drex.py
```

It runs a two-datapoint experiment. The `grounded` evaluator sends the question, the context and the app's answer to Drex and returns the probability that every claim in the answer is supported by the context. Drex returns a probability, not a verdict, so you pick the pass threshold after the run: filter or compare runs on the metric instead of fixing a cutoff in the evaluator.

Things to know:

- HoneyHive names the metric after the evaluator function's name, so keep it stable across runs to compare them.
- Each evaluator call is one Drex request and is billed as one. Keep `max_workers` low if you are on a rate-limited plan.
- The data in `eval_drex.py` is synthetic.

## Verified

Run against `console.nace.ai` with `drex-max`, `honeyhive` 1.8.1, `typesafe-sdk` 0.7.5 and `openinference-instrumentation-typesafe` 0.1.7: both scripts ran to completion, and the traced session was read back through the HoneyHive SDK with the model name and typed answers. Not run: the HoneyHive UI itself, and `Score` questions as evaluators.
