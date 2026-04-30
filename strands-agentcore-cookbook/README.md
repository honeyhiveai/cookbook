# Strands + AWS Bedrock AgentCore Cookbook

A minimal, single-file Strands agent deployed via the [AWS Bedrock AgentCore](https://aws.github.io/bedrock-agentcore-starter-toolkit/) runtime, with HoneyHive observability wired in.

## What this cookbook is

This is the reference output of HoneyHive's `honeyhive-instrument` skill applied to a Strands + AgentCore project. To produce it yourself in your own repo, install the skill in VS Code Copilot:

    gh skill install honeyhiveai/skills honeyhive-instrument

Then in VS Code Copilot agent mode (the Chat view), ask:

    Instrument this Strands agent with HoneyHive.

Copilot picks up the skill via its description, detects the Strands + AgentCore stack, installs honeyhive + the OpenInference instrumentor, initializes the tracer, and validates that traces appear in HoneyHive Studio. The rest of this README explains what the skill produced and how to deploy / run it.

## Prereqs

- Python 3.12
- AWS profile with Bedrock model access (Claude Sonnet 4.0 enabled in your account / region)
- HoneyHive project + API key
- VS Code with GitHub Copilot signed in (for the workshop / skill flow)

Docker is not required when using the default `agentcore deploy` flow — AgentCore builds via CodeBuild.

## What the skill produced

- `agent.py` — single-file Strands agent: `@tool` decorators on `calculator` and `current_time`, a `BedrockModel`, and an `@app.entrypoint` for the AgentCore runtime.
- `HoneyHiveTracer.init(...)` — runs at module load, before agent construction, so the tracer's provider is ready when Strands starts emitting spans.
- `StrandsAgentsToOpenInferenceProcessor` — attached to the tracer's provider; maps Strands' `gen_ai.*` OTEL spans into the agent / llm / tool kinds HoneyHive renders natively.
- `requirements.txt` — version-pinned with one-line rationale per pin.
- `.bedrock_agentcore.yaml.example` — template for the AgentCore CLI deployment config (the real `.bedrock_agentcore.yaml` is gitignored at runtime).

## Setup

```bash
pip install -r requirements.txt
```

Set the env vars (matches the public docs at https://docs.honeyhive.ai/v2/integrations/strands):

```bash
export HH_API_KEY=...
export HH_PROJECT=...
# Optional — override the default Claude Sonnet 4.0 model, e.g. for an
# application-inference-profile ARN:
# export BEDROCK_MODEL_ID=arn:aws:bedrock:us-east-1:...:application-inference-profile/...
```

## Local test

```bash
agentcore launch --local
curl -X POST localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What is 17 * 23?"}'
```

## Deploy

```bash
agentcore configure -e agent.py
agentcore launch
```

## Invoke

```bash
agentcore invoke '{"prompt": "What time is it?"}'
```

## Verify in HoneyHive Studio

Open HoneyHive Studio, find the session for your runtime, and confirm spans are typed `agent` / `llm` / `tool` (not all surfaced as `tool`). If everything is `tool`, the OpenInference processor is not attached — re-check `agent.py`.

## Cleanup

```bash
agentcore destroy
```

(Verify the exact teardown command in the [AgentCore starter toolkit docs](https://aws.github.io/bedrock-agentcore-starter-toolkit/) — the CLI surface is still evolving.)

## Extension points

`agent.py` has `# TODO:` markers for adding more tools without re-running the skill. Drop a new `@tool` function and add it to the `Agent(tools=[...])` list — for example, a `lookup_customer(customer_id)` stub. The HoneyHive session will pick it up automatically; no tracer changes needed.
