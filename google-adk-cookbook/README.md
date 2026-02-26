# Google ADK Multi-Agent Cookbook

End-to-end example: build a multi-agent customer support bot with [Google ADK](https://google.github.io/adk-docs/) and add observability + evaluation with [HoneyHive](https://honeyhive.ai).

## What's in here

| File | What it does |
|------|-------------|
| `main.py` | Multi-agent support app with HoneyHive tracing, enrichment, and custom spans |
| `evaluate.py` | Run the agent against a test dataset and measure quality with HoneyHive experiments |

## Architecture

A coordinator agent routes customer queries to two specialists:

```
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

The coordinator uses ADK's native `sub_agents` delegation -- the LLM decides which specialist to route to based on agent descriptions.

## Setup

**Prerequisites**: Python 3.11+, a HoneyHive account, a Google AI API key.

1. Clone this repo and cd into this directory:

```bash
git clone https://github.com/honeyhiveai/cookbook.git
cd cookbook/google-adk-cookbook
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Set environment variables (create a `.env` file):

```bash
HH_API_KEY=your-honeyhive-api-key
HH_PROJECT=your-project-name
GOOGLE_API_KEY=your-google-ai-api-key
OPENAI_API_KEY=your-openai-key  # only needed for evaluate.py
```

## Run

### Tracing demo

```bash
python main.py
```

Sends 3 customer queries through the multi-agent system. Check your HoneyHive dashboard to see:
- Coordinator routing decisions
- Sub-agent delegation and tool calls
- Session enrichment (user ID, environment)
- Custom spans for input preprocessing

### Evaluation

```bash
python evaluate.py
```

Runs 8 test queries through the agent and evaluates response quality using:
- **response_quality**: LLM-as-judge scoring (0-1) for helpfulness, accuracy, and tone
- **correct_routing**: LLM-as-judge check for correct specialist routing

Results appear in the HoneyHive experiments UI.

## What HoneyHive adds

Each step in `main.py` highlights a HoneyHive capability:

| Step | Code | What you get |
|------|------|-------------|
| Auto-tracing | `HoneyHiveTracer.init()` + `GoogleADKInstrumentor()` | Agent runs, LLM calls, tool calls traced automatically |
| Enrichment | `tracer.enrich_session(...)` | Filter traces by user, environment, app version |
| Custom spans | `@trace()` decorator | Trace your own business logic alongside agent spans |
| Evaluation | `evaluate()` in evaluate.py | Measure agent quality against a dataset |

## Resources

- [HoneyHive Docs](https://docs.honeyhive.ai)
- [Google ADK Docs](https://google.github.io/adk-docs/)
- [ADK Multi-Agent Systems](https://google.github.io/adk-docs/agents/multi-agents/)
