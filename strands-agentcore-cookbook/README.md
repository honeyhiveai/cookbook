# Strands + AWS Bedrock AgentCore Cookbook

A minimal, single-file Strands agent deployed via [AWS Bedrock AgentCore](https://aws.github.io/bedrock-agentcore-starter-toolkit/), with HoneyHive observability wired in.

This is the reference output of HoneyHive's `honeyhive-instrument` skill. To produce it yourself in your own repo:

```bash
# Install the skill
gh skill install honeyhiveai/skills honeyhive-instrument

# Then in VS Code Copilot agent mode (Chat view), ask:
# "Instrument this Strands agent with HoneyHive."
```

Copilot detects the Strands + AgentCore stack, installs honeyhive + the OpenInference instrumentor, initializes the tracer, and validates that traces appear in HoneyHive Studio.

## Quickstart

```bash
# Install
pip install -r requirements.txt

# Set env vars (see https://docs.honeyhive.ai/v2/integrations/strands)
export HH_API_KEY=...
export HH_PROJECT=...
# Optional: override the default Claude Sonnet 4.0 model
# export BEDROCK_MODEL_ID=arn:aws:bedrock:us-east-1:...:application-inference-profile/...

# Run locally
agentcore configure -e agent.py
agentcore launch --local
curl -X POST localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What is 17 * 23?"}'

# Deploy to AWS
agentcore launch
agentcore invoke '{"prompt": "What time is it?"}'

# Cleanup
agentcore destroy
```

## What's in the box

- **`agent.py`** — Strands agent with `calculator` and `current_time` tools, a `BedrockModel`, and an `@app.entrypoint` for the AgentCore runtime.
- **`HoneyHiveTracer.init(...)`** — runs at module load *before* importing strands so auto-instrumentation hooks register against Strands' OpenTelemetry tracer provider. The rc21+ SDK maps Strands' `gen_ai.*` spans into HoneyHive's native agent / llm / tool types.
- **`requirements.txt`** — version-pinned dependencies.

## Prereqs

- Python 3.12+
- AWS credentials with Bedrock model access (Claude Sonnet 4.0 enabled in your account/region)
- HoneyHive project + API key

For full AWS resource details, IAM requirements, and service quotas see [infra_reqs.md](infra_reqs.md).

## Verify in HoneyHive Studio

Open HoneyHive Studio and confirm spans are typed `agent` / `llm` / `tool`. If everything shows as `tool`, auto-instrumentation didn't attach — verify that `HoneyHiveTracer.init(...)` runs **before** `from strands import ...` in `agent.py`.

## Extending

Add a new `@tool` function in `agent.py` and include it in the `Agent(tools=[...])` list. HoneyHive picks it up automatically — no tracer changes needed.
