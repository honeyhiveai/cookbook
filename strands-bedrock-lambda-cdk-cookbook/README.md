# Strands + Bedrock + Lambda (CDK) Cookbook

A Python CDK scaffold for deploying a Strands agent that calls AWS Bedrock from within a Lambda function, traced with HoneyHive. This is a placeholder skeleton — the Lambda handler, CDK stack resources, and HoneyHive tracer wiring will be filled in by follow-up work.

## Prerequisites

- Python 3.9+
- Node.js (for the CDK CLI — `npm i -g aws-cdk`, or use `npx cdk`)
- AWS credentials configured (`aws configure` or `AWS_*` env vars)

## Synth

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
npx --yes cdk synth
```

`cdk synth` emits CloudFormation to `cdk.out/`. The stack currently synthesizes empty; resources land in follow-up PRs.

## Version pins

`lambda/requirements.txt` uses exact pins — reproducibility over flexibility. The HoneyHive SDK is pinned to `1.0.0rc21` because it's the earliest rc with both the session_id baggage isolation (prevents warm-Lambda session bleed across users) and the event_type priority detection that routes Strands GenAI ops (`invoke_agent` → chain, `execute_tool` → tool, `chat` → model) instead of falling through to the generic `tool` default. See the header of `lambda/requirements.txt` for the full rationale.
