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

## AWS resources provisioned

When you run `agentcore launch`, the AgentCore CLI creates these resources in YOUR AWS account:

- **IAM execution role** — auto-created by the toolkit. Just enough permission for the runtime to invoke Bedrock on your agent's behalf. You'll see it in IAM console as `bedrock-agentcore-runtime-<agent-name>`.
- **S3 bucket** (default `direct_code_deploy` mode) — staging bucket where your packaged Python code is uploaded for the runtime to fetch. Named `bedrock-agentcore-<account>-<region>` or similar.
- **ECR repository** — only if you opt into container deploy mode (default is direct-code, so skip this).

What is **NOT** created:
- No Lambda function. Your code runs in AWS-managed AgentCore Runtime, not customer Lambda.
- No API Gateway. Invocation goes through the `bedrock-agentcore` service API (`agentcore invoke` calls it).
- No CloudFormation stack. The toolkit calls AWS APIs directly; nothing to inspect in the CFN console.
- No Secrets Manager wiring. Secrets pass through env vars at runtime.

Cleanup is `agentcore destroy` (or whatever the CLI's teardown command is in your installed version) — it removes the runtime, the IAM role, and the S3 staging objects.

## AWS dependencies required

To run this cookbook end-to-end you need:

- **An AWS account with valid credentials.** SSO via IAM Identity Center is recommended for workshops. For the May 21 NW Accelerator Fair, attendees use the NW-provided sandbox via `aws sso login --profile workshop`.
- **Region with Bedrock model availability.** Default `us-east-1`. Other regions vary in Claude Sonnet 4.0 availability.
- **Bedrock model access enabled.** Manual step in the AWS Console → Bedrock → Model access → enable "Anthropic Claude Sonnet 4.0" (or the model you target). This is per-account, per-region, and propagation can take a few minutes.
- **AgentCore Runtime service quotas.** Default per-account quotas may be low (single-digit concurrent runtimes). For multi-attendee workshops, file a service-limit-increase ticket with AWS Support 1-2 weeks ahead.
- **IAM permissions on your caller profile.** The toolkit needs to create an execution role and S3 bucket on your behalf, plus invoke AgentCore. Roughly: `bedrock-agentcore:*`, `iam:CreateRole`, `iam:PassRole`, `s3:CreateBucket`, `s3:PutObject`. (Sandbox SSO roles in workshop environments typically have this; in production accounts, check with your AWS admin.)
- **Application-inference-profile ARN** (optional). If you need per-tenant chargeback or NW-style cross-region inference profiles, set `BEDROCK_MODEL_ID=arn:aws:bedrock:us-east-1:<account>:application-inference-profile/<profile-id>` in your env.

## What the skill produced

- `agent.py` — single-file Strands agent: `@tool` decorators on `calculator` and `current_time`, a `BedrockModel`, and an `@app.entrypoint` for the AgentCore runtime.
- `HoneyHiveTracer.init(...)` — runs at module load **before importing strands**, so HoneyHive's auto-instrumentation hooks register against Strands' OpenTelemetry tracer provider. The rc21+ SDK then maps Strands' `gen_ai.*` spans into the agent / llm / tool kinds HoneyHive renders natively — no separate processor wiring required.
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

Open HoneyHive Studio, find the session for your runtime, and confirm spans are typed `agent` / `llm` / `tool` (not all surfaced as `tool`). If everything is `tool`, auto-instrumentation didn't attach — verify in `agent.py` that `HoneyHiveTracer.init(...)` runs **before** `from strands import ...`.

## Cleanup

```bash
agentcore destroy
```

(Verify the exact teardown command in the [AgentCore starter toolkit docs](https://aws.github.io/bedrock-agentcore-starter-toolkit/) — the CLI surface is still evolving.)

## Extension points

`agent.py` has `# TODO:` markers for adding more tools without re-running the skill. Drop a new `@tool` function and add it to the `Agent(tools=[...])` list — for example, a `lookup_customer(customer_id)` stub. The HoneyHive session will pick it up automatically; no tracer changes needed.
