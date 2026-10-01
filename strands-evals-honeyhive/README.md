# Strands Evals × HoneyHive

Run [Strands Evals](https://pypi.org/project/strands-agents-evals/) evaluators on agent sessions that are already in HoneyHive, and write the scores back to those sessions.

Strands Evals can evaluate traces that it reads from an observability backend through a `TraceProvider`. This cookbook adds `HoneyHiveProvider`, which reads a HoneyHive session and converts it to the trajectory that Strands Evals evaluators expect. The agent does not run again during evaluation.

The provider works for agents built with the Strands **Python** SDK and the Strands **TypeScript** SDK. Strands Evals is Python-only, so this is how you run its evaluators on a TypeScript agent: the agent sends traces to HoneyHive, and a Python step scores them.

## What it maps

| Strands span in HoneyHive | Strands Evals span |
| --- | --- |
| `invoke_agent <name>` | `AgentInvocationSpan`: user prompt, final response, available tools |
| `chat` (model event) | `InferenceSpan`: the message history, including tool calls and tool results |
| `execute_tool <name>` | `ToolExecutionSpan`: tool name, arguments, result |

Event loop cycle spans and the session event carry nothing the evaluators read, so the provider skips them. Spans are grouped into traces by their OpenTelemetry trace ID.

## Prerequisites

| Requirement | Where to get it |
| --- | --- |
| Python 3.11+ | [python.org](https://www.python.org/downloads/) |
| A HoneyHive session from a Strands agent | Trace a Strands agent with [the Strands integration](https://docs.honeyhive.ai/v2/integrations/strands), or run [strands-ts-offline-evals](../strands-ts-offline-evals) |
| HoneyHive API key | [HoneyHive dashboard](https://app.honeyhive.ai), under your project's API keys |
| OpenAI API key | [platform.openai.com/api-keys](https://platform.openai.com/api-keys). Used by the evaluators' judge model. |

## Setup

```bash
cd strands-evals-honeyhive
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill in `.env`:

```bash
HH_API_KEY=your_honeyhive_api_key
OPENAI_API_KEY=your_openai_api_key
```

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `HH_API_KEY` | Yes | | API key for the HoneyHive project that holds the sessions |
| `HH_API_URL` | No | `https://api.dp1.us.prod.honeyhive.ai` | HoneyHive API host. Change it for dedicated or self-hosted deployments. |
| `OPENAI_API_KEY` | Yes | | Key for the judge model |

## Run

Pass one or more HoneyHive session IDs:

```bash
python example.py <session_id> [<session_id> ...]
```

The example runs `HelpfulnessEvaluator` and `ToolSelectionAccuracyEvaluator` on each session. It then writes the scores to the session as `strands.HelpfulnessEvaluator` and `strands.ToolSelectionAccuracyEvaluator` metrics, each with an `_explanation` metric that holds the judge's reason. The scores appear on the session in HoneyHive, next to any metrics the session already has.

To find session IDs, open **Traces** in HoneyHive, or read `event_ids` from an experiment run with the API.

## Use the provider in your own code

Copy `honeyhive_provider.py` into your project:

```python
from strands_evals import Case, Experiment
from strands_evals.evaluators import GoalSuccessRateEvaluator

from honeyhive_provider import HoneyHiveProvider

provider = HoneyHiveProvider()  # Reads HH_API_KEY and HH_API_URL
cases = [Case(name="refund-flow", session_id="<honeyhive-session-id>", input="refund-flow")]
report = Experiment(cases=cases, evaluators=[GoalSuccessRateEvaluator()]).run_evaluations(provider.as_task())
```

Strands Evals judges use Amazon Bedrock by default. Pass `model=` to an evaluator to use another provider, as `example.py` does.

## Test

The tests use two recorded HoneyHive sessions, one from a Python Strands agent and one from a TypeScript Strands agent. They do not call the network.

```bash
pytest tests
```

## Limitations

- The provider reads Strands spans. Sessions from other frameworks convert only when their span names match `invoke_agent`, `chat`, and `execute_tool`.
- `available_tools` holds tool names only. HoneyHive does not store tool parameter schemas on the agent span.
- HoneyHive indexes new sessions shortly after they arrive. A session that is a few minutes old can return no events yet. Retry after a short wait.

## Learn more

- [Trace Strands Agents with HoneyHive](https://docs.honeyhive.ai/v2/integrations/strands)
- [Strands Evals on PyPI](https://pypi.org/project/strands-agents-evals/)
