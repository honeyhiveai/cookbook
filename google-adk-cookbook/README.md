# Google ADK Multi-Agent Cookbook

This cookbook currently targets the HoneyHive beta SDK release line.

End-to-end example: build a multi-agent customer support bot with [Google ADK](https://google.github.io/adk-docs/), add observability with [HoneyHive](https://honeyhive.ai), and use an evaluation run to catch a quality regression.

The cookbook ships two versions of the same agent so you can see the before/after side by side in HoneyHive:

- `agent_v1.py` — initial agent with vague tool docstrings and minimal instructions. The agent has to guess internal enum codes and often fails.
- `agent_v2.py` — improved agent. Same tools, same enum codes, but with detailed docstrings and clearer delegation rules. The agent routes and calls tools correctly.

## What's in here

| File               | What it does                                                                              |
| ------------------ | ----------------------------------------------------------------------------------------- |
| `main.py`          | Thin runner: loads the selected agent version and sends one query with HoneyHive tracing  |
| `evaluate.py`      | Runs the selected agent across a 5-query dataset and scores responses with an LLM judge    |
| `agent_v1.py`      | Initial (degraded) agent used as the "before" baseline                                     |
| `agent_v2.py`      | Improved agent used as the "after" comparison                                              |
| `requirements.txt` | Python dependencies for the cookbook                                                       |

## Architecture

A coordinator agent routes customer queries to two specialists:

```text
Customer Query
      |
  [coordinator]
      |
  +---+---+
  |       |
billing  technical
agent    agent
  |       |
lookup   search
billing  knowledge_base
```

The coordinator uses ADK's native `sub_agents` delegation. The model decides which specialist to call based on each agent's description and instructions.

## Setup

Prerequisites:

- Python 3.11+
- A HoneyHive account
- A Google Gemini API key

1. Clone the repo and enter this directory:

```bash
git clone https://github.com/honeyhiveai/cookbook.git
cd cookbook/google-adk-cookbook
```

2. Create a virtual environment and install dependencies:

```bash
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

3. Create a `.env` file:

```bash
HH_API_KEY=your-honeyhive-api-key
HH_PROJECT=your-project-name
HH_API_URL=https://api.honeyhive.ai  # optional, override for non-production environments
GOOGLE_API_KEY=your-gemini-api-key
```

## Run

### Tracing demo

Run the degraded agent once and inspect its trace in HoneyHive:

```bash
uv run python main.py --version v1
```

Then run the improved agent:

```bash
uv run python main.py --version v2
```

For the same query ("I was charged $24.50 but I thought that was refunded?") you should see:

- **v1**: the agent fails to call `lookup_billing` with the right enum, apologizes, and asks the customer for a transaction ID.
- **v2**: the agent delegates to `billing_agent`, calls `lookup_billing` with `query_type="BIL_RMA_03"`, and returns the refund ID and status.

Both runs show up in HoneyHive with the same spans and `agent_version` metadata so you can compare them directly.

### Evaluation

Run the evaluation for each version:

```bash
uv run python evaluate.py --version v1
uv run python evaluate.py --version v2
```

Each run sends 5 queries through the agent and scores each response with an LLM-as-judge (`response_quality`) on a strict 3-point scale:

- `1` – fully helpful (concrete amounts, dates, article IDs, or troubleshooting steps)
- `0.5` – partially helpful (addresses the question but vague or incomplete)
- `0` – unhelpful (apologizes, admits a tool error, or dodges the question)

In HoneyHive, open the two runs (`customer-support-eval-v1` and `customer-support-eval-v2`) and compare the `response_quality` aggregate. v2 typically scores near 1.0 while v1 scores well below that.

## Implementation notes

- **`max_llm_calls=15`**: `main.py` caps agent iterations via `RunConfig` so a confused agent fails fast instead of looping through many tool-call retries. When the v1 agent exhausts the cap it returns a clear `[agent gave up: ...]` response that the judge correctly scores as 0.
- **HoneyHive summary fetch**: on the current pre-release SDK, the client-side aggregate parse at the end of `evaluate()` can raise a `pydantic.ValidationError`. The run itself uploads successfully, so `evaluate.py` catches the error and points you at the HoneyHive UI for the scores. This will go away once we pin a newer SDK release.

## What HoneyHive adds

| Capability   | Code                                                 | Value                                                          |
| ------------ | ---------------------------------------------------- | -------------------------------------------------------------- |
| Auto-tracing | `HoneyHiveTracer.init()` + `GoogleADKInstrumentor()` | Captures agent runs, model calls, and tool calls automatically |
| Enrichment   | `tracer.enrich_session(...)`                         | Adds user, plan, and environment metadata to traces            |
| Custom spans | `@trace()` on `load_customer_context()`              | Captures your own business logic alongside framework spans     |
| Evaluation   | `evaluate()`                                         | Measures quality over a repeatable dataset                     |

## Resources

- [HoneyHive Docs](https://docs.honeyhive.ai)
- [Google ADK Docs](https://google.github.io/adk-docs/)
- [ADK Multi-Agent Systems](https://google.github.io/adk-docs/agents/multi-agents/)
