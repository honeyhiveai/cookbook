# Google ADK Multi-Agent Cookbook

This cookbook currently targets the HoneyHive beta SDK release line.

End-to-end example: build a multi-agent customer support bot with [Google ADK](https://google.github.io/adk-docs/) and add observability plus evaluation with [HoneyHive](https://honeyhive.ai).

## What's in here

| File | What it does |
|------|-------------|
| `main.py` | Runs a coordinator agent plus billing and technical specialists with HoneyHive tracing |
| `evaluate.py` | Runs the same agent against a small dataset and scores outputs with HoneyHive experiments |
| `requirements.txt` | Python dependencies for the cookbook |

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
- A Google AI API key
- An OpenAI API key for `evaluate.py`

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

This installs the latest available HoneyHive beta SDK together with the other cookbook dependencies.

3. Create a `.env` file:

```bash
HH_API_KEY=your-honeyhive-api-key
HH_PROJECT=your-project-name
HH_API_URL=https://api.honeyhive.ai  # optional, override for non-production environments
GOOGLE_API_KEY=your-google-ai-api-key
OPENAI_API_KEY=your-openai-key
```

## Run

### Tracing demo

```bash
uv run python main.py
```

This sends three customer queries through the multi-agent system. In HoneyHive, you'll see:

- Coordinator routing decisions
- Sub-agent delegation and tool calls
- Session enrichment with business context
- Custom spans for customer context loading

### Evaluation

```bash
uv run python evaluate.py
```

This runs eight test queries through the agent and evaluates:

- `response_quality`: LLM-as-judge scoring for helpfulness, accuracy, and tone
- `correct_routing`: LLM-as-judge verification that the right specialist handled the query

## What HoneyHive adds

| Capability | Code | Value |
|-----------|------|-------|
| Auto-tracing | `HoneyHiveTracer.init()` + `GoogleADKInstrumentor()` | Captures agent runs, model calls, and tool calls automatically |
| Enrichment | `tracer.enrich_session(...)` | Adds user, plan, and environment metadata to traces |
| Custom spans | `@trace()` on `load_customer_context()` | Captures your own business logic alongside framework spans |
| Evaluation | `evaluate()` | Measures quality over a repeatable dataset |

## Resources

- [HoneyHive Docs](https://docs.honeyhive.ai)
- [Google ADK Docs](https://google.github.io/adk-docs/)
- [ADK Multi-Agent Systems](https://google.github.io/adk-docs/agents/multi-agents/)
