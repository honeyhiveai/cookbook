# Infrastructure Requirements

Detailed AWS prerequisites and resource inventory for deploying this cookbook.

## AWS resources provisioned

When you run `agentcore launch`, the AgentCore CLI creates these resources in your AWS account:

- **IAM execution role** — auto-created by the toolkit. Just enough permission for the runtime to invoke Bedrock on your agent's behalf. You'll see it in IAM console as `bedrock-agentcore-runtime-<agent-name>`.
- **S3 bucket** (default `direct_code_deploy` mode) — staging bucket where your packaged Python code is uploaded for the runtime to fetch. Named `bedrock-agentcore-<account>-<region>` or similar.
- **ECR repository** — only if you opt into container deploy mode (default is direct-code, so skip this).

What is **NOT** created:
- No Lambda function. Your code runs in AWS-managed AgentCore Runtime, not customer Lambda.
- No API Gateway. Invocation goes through the `bedrock-agentcore` service API (`agentcore invoke` calls it).
- No CloudFormation stack. The toolkit calls AWS APIs directly; nothing to inspect in the CFN console.
- No Secrets Manager wiring. Secrets pass through env vars at runtime.

Cleanup is `agentcore destroy` — it removes the runtime, the IAM role, and the S3 staging objects.

## AWS dependencies required

To run this cookbook end-to-end you need:

- **An AWS account with valid credentials.** SSO via IAM Identity Center is recommended. For workshop environments, use the provided sandbox profile (e.g. `aws sso login --profile workshop`).
- **Region with Bedrock model availability.** Default `us-east-1`. Other regions vary in Claude Sonnet 4.0 availability.
- **Bedrock model access enabled.** Manual step in the AWS Console → Bedrock → Model access → enable "Anthropic Claude Sonnet 4.0" (or the model you target). This is per-account, per-region, and propagation can take a few minutes.
- **AgentCore Runtime service quotas.** Default per-account quotas may be low (single-digit concurrent runtimes). For multi-attendee workshops, file a service-limit-increase ticket with AWS Support 1–2 weeks ahead.
- **IAM permissions on your caller profile.** The toolkit needs to create an execution role and S3 bucket on your behalf, plus invoke AgentCore. Roughly: `bedrock-agentcore:*`, `iam:CreateRole`, `iam:PassRole`, `s3:CreateBucket`, `s3:PutObject`. Sandbox SSO roles in workshop environments typically have this; in production accounts, check with your AWS admin.
- **Application-inference-profile ARN** (optional). For per-tenant chargeback or cross-region inference profiles, set `BEDROCK_MODEL_ID=arn:aws:bedrock:us-east-1:<account>:application-inference-profile/<profile-id>` in your env.

## What the skill produced

This cookbook is the reference output of HoneyHive's `honeyhive-instrument` skill applied to a Strands + AgentCore project. To reproduce it in your own repo, install the skill in VS Code Copilot:

```
gh skill install honeyhiveai/skills honeyhive-instrument
```

Then in VS Code Copilot agent mode, ask:

```
Instrument this Strands agent with HoneyHive.
```

Copilot detects the Strands + AgentCore stack, installs honeyhive + the OpenInference instrumentor, initializes the tracer, and validates that traces appear in HoneyHive Studio.

### Files produced

- `agent.py` — single-file Strands agent: `@tool` decorators on `calculator` and `current_time`, a `BedrockModel`, and an `@app.entrypoint` for the AgentCore runtime.
- `HoneyHiveTracer.init(...)` — runs at module load **before importing strands**, so HoneyHive's auto-instrumentation hooks register against Strands' OpenTelemetry tracer provider. The rc21+ SDK then maps Strands' `gen_ai.*` spans into the agent / llm / tool kinds HoneyHive renders natively — no separate processor wiring required.
- `requirements.txt` — version-pinned with one-line rationale per pin.
- `.bedrock_agentcore.yaml.example` — template for the AgentCore CLI deployment config (the real `.bedrock_agentcore.yaml` is gitignored at runtime).

Docker is not required when using the default `agentcore deploy` flow — AgentCore builds via CodeBuild.
