# Strands + AWS Bedrock AgentCore Cookbook

A minimal, single-file Strands agent deployed via the [AWS Bedrock AgentCore](https://aws.github.io/bedrock-agentcore-starter-toolkit/) runtime, with HoneyHive observability wired in.

This is the scaffold. The full README — setup, architecture diagrams, demo walkthroughs, evaluation guidance — is coming in a follow-up sub-issue (HHAI-4969).

## Files

| File                                | What it is                                                                  |
| ----------------------------------- | --------------------------------------------------------------------------- |
| `agent.py`                          | Single-file Strands agent + AgentCore `@app.entrypoint`. HoneyHive at load. |
| `requirements.txt`                  | Python deps (bedrock-agentcore, strands-agents, honeyhive, OI processor)    |
| `.bedrock_agentcore.yaml.example`   | Template for the AgentCore deployment config (gitignored at runtime)        |
| `.gitignore`                        | Python + AWS + the auto-generated `.bedrock_agentcore.yaml`                 |

## Quick local run

```bash
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt

# Create .env with HH_API_KEY, HH_PROJECT, AWS_REGION (and AWS creds in your shell)

agentcore configure -e agent.py
agentcore launch --local
curl -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What is 17 * 23?"}'
```

The trace shows up in HoneyHive with the agent / llm / tool span typing produced by the OpenInference Strands span processor.

> Full setup, deployment, and demo guide → HHAI-4969.
