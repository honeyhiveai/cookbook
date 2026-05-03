# Strands + Bedrock + Lambda (CDK) Cookbook

Deploy a [Strands](https://strandsagents.com) agent that calls AWS Bedrock from an AWS Lambda function, fronted by an HTTP API, and fully traced with [HoneyHive](https://docs.honeyhive.ai). One `cdk deploy` and you have a working, observable agent endpoint.

## What's in here

- `app.py` — CDK app entry point.
- `stacks/strands_bedrock_lambda_stack.py` — Lambda + IAM + HTTP API + Secrets Manager wiring.
- `lambda/handler.py` — Strands agent with a calculator tool, wrapped in a HoneyHive session per invocation.
- `lambda/requirements.txt` — runtime deps shipped into the Lambda package.
- `requirements.txt` — CDK synth deps (host-side only).

## Prerequisites

- **AWS CLI** configured with credentials that can create Lambda, IAM roles, API Gateway, and Secrets Manager resources: `aws configure`.
- **Node.js 18+** so you can run the CDK CLI (`npm i -g aws-cdk`, or prefix every `cdk` command with `npx --yes`).
- **Python 3.12** — the Lambda runtime is pinned to 3.12, so match it locally to avoid native-wheel surprises at build time.
- **Docker** running locally — `cdk deploy` bundles the Lambda's Python dependencies inside the official AWS Lambda Python 3.12 image, so the Docker daemon must be up before you deploy.
- **AWS Bedrock model access.** Claude and Nova models require separate access grants in the Bedrock console (*Model access* → *Manage model access*). Grant access before deploying.
- **A HoneyHive project + API key.** Create them at [app.honeyhive.ai](https://app.honeyhive.ai) and keep the key handy for step 4. See the [HoneyHive quickstart](https://docs.honeyhive.ai/introduction/quickstart) if you need a walkthrough.

## Workshop setup

If you're following along during the Nationwide hackathon, the live edit segment is demoed in VS Code with GitHub Copilot. Skip this section if you're working through the cookbook on your own.

**1. Install VS Code.** Download from [code.visualstudio.com](https://code.visualstudio.com/).

**2. Install GitHub Copilot.** Open the Extensions panel (`cmd+shift+X` / `ctrl+shift+X`), search for *GitHub Copilot*, install it. The companion *GitHub Copilot Chat* extension installs alongside — keep it enabled.

**3. Sign in.** Run *GitHub Copilot: Sign In* from the command palette (`cmd+shift+P` / `ctrl+shift+P`) and authorize through GitHub. Nationwide attendees already have org-issued Copilot seats; if the sign-in prompt says you don't have access, flag it to the workshop host.

**4. Confirm settings.** Open Settings (`cmd+,` / `ctrl+,`) and verify:

- `editor.inlineSuggest.enabled` is on (default).
- `github.copilot.enable` is `*` (all languages).
- Copilot Chat opens with `cmd+ctrl+I` on macOS, `ctrl+alt+I` on Windows/Linux — dock it next to the editor while you work.

**Using Copilot during the live edit.** The customization segment touches `lambda/handler.py` — the `calculator` tool, the agent's `system_prompt`, and the `Agent(tools=[...])` wiring are the spots we'll edit. `Tab` accepts the inline suggestion, `alt+]` / `alt+[` cycles through alternates, and `cmd+ctrl+I` (or `ctrl+alt+I`) opens Chat — paste the function and ask for an explanation if a suggestion looks off. Treat suggestions as drafts; read before accepting.

**Venue Wi-Fi flaky?** Copilot needs network. If it drops, the deploy steps below stand alone — every command is copy-pasteable, and the *Common errors* section covers the failures you're likely to hit.

## Setup

All commands run from `strands-bedrock-lambda-cdk-cookbook/`.

**1. Clone and enter the cookbook.**

```bash
git clone https://github.com/honeyhiveai/cookbook.git
cd cookbook/strands-bedrock-lambda-cdk-cookbook
```

**2. Create a virtualenv and install CDK synth deps.**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**3. Bootstrap CDK for your AWS account + region (one-time, per account/region).**

```bash
npx --yes cdk bootstrap
```

**4. Store your HoneyHive API key in Secrets Manager.**

The stack reads the key at deploy time via a CloudFormation dynamic reference — the plaintext never lands in the synthesized template.

```bash
export HONEYHIVE_API_KEY="hh-..."
aws secretsmanager create-secret \
  --name honeyhive/api-key \
  --secret-string "$HONEYHIVE_API_KEY"
```

**5. Pick a Bedrock model ARN.**

For Claude Sonnet 4.5, Nova, and anything with chargeback tagging, use an **application-inference-profile** ARN. For everything else a regular inference-profile or foundation-model ARN works.

```bash
# Example: application inference profile you created in your account
export MODEL_ARN="arn:aws:bedrock:us-east-1:123456789012:application-inference-profile/abcd1234"
```

List available inference profiles with:

```bash
aws bedrock list-inference-profiles --region us-east-1
```

**6. Deploy.**

Pass your HoneyHive project name and model ARN as CDK context. Everything else has sensible defaults — see the *Customization* section to override.

```bash
npx --yes cdk deploy \
  -c honeyhive_project=my-project \
  -c model_arn="$MODEL_ARN"
```

CDK prints three outputs when the stack finishes:

- `StrandsBedrockLambdaStack.ApiUrl` — the HTTP API base URL.
- `StrandsBedrockLambdaStack.LambdaArn` — the deployed function.
- `StrandsBedrockLambdaStack.RoleArn` — the Lambda execution role (useful for debugging IAM).

Copy the `ApiUrl` value — you'll use it next.

## Invoke & verify

```bash
export API_URL="https://xxxxx.execute-api.us-east-1.amazonaws.com"  # from the ApiUrl output

curl -s -X POST "$API_URL/invoke" \
  -H 'content-type: application/json' \
  -d '{"prompt": "what is 17 * 23?"}'
```

The response shape:

```json
{
  "response": "17 * 23 = 391",
  "session_url": "https://app.honeyhive.ai/my-project/sessions/<uuid>",
  "session_id": "<uuid>"
}
```

Open the `session_url` in your browser. Within ~15 seconds you should see a trace in HoneyHive Studio with:

- A **session** span (`lambda-<hex>`) wrapping the whole invocation.
- A **model** span for the Bedrock Converse call (input prompt, output completion, token counts).
- A **tool** span for the `calculator` function call.

If the trace doesn't appear, jump to *Common errors* below.

## Common errors

**`ValidationException: ... on-demand throughput isn't supported`**

Your `model_arn` points at a foundation-model ARN for a model that only supports provisioned or inference-profile throughput (common for Claude 4.5 and Nova). Switch to the **inference-profile** or **application-inference-profile** ARN for that model. `aws bedrock list-inference-profiles` will show you what's available.

**`AccessDeniedException` on `bedrock:InvokeModel`**

The execution role is missing a resource pattern the model ARN doesn't match. The stack grants `foundation-model/*`, `inference-profile/*`, and `application-inference-profile/*` by default — if you've customized the stack and narrowed these, add the missing pattern back. Double-check with:

```bash
aws iam get-role-policy --role-name <RoleArn from output> --policy-name <policy name>
```

**Trace never appears in HoneyHive Studio**

Walk through these in order:

1. `aws secretsmanager get-secret-value --secret-id honeyhive/api-key` — confirm the secret exists and the value is your real key.
2. Check the Lambda log group (`/aws/lambda/<function-name>`) for a cold-start error like `RuntimeError: HONEYHIVE_API_KEY and HONEYHIVE_PROJECT must be set`.
3. Confirm the `HONEYHIVE_PROJECT` value you deployed with matches a project that actually exists in your HoneyHive workspace. Typos produce a silent drop.
4. If you're on a self-hosted HoneyHive, pass `-c honeyhive_server_url=https://your-host` at deploy time.

**Session bleed across warm invocations** (one user sees another user's prompt/response in their session)

You're on an old HoneyHive SDK. The `lambda/requirements.txt` in this cookbook pins the version that ships the `with_session()` ContextVar fix. Re-install and redeploy:

```bash
rm -rf lambda/.venv cdk.out
npx --yes cdk deploy -c honeyhive_project=my-project -c model_arn="$MODEL_ARN"
```

**Claude 4.5 or Nova returns a validation error even with the right ARN**

Those models require an **application-inference-profile** ARN — a plain inference-profile or foundation-model ARN won't work. Create an application inference profile in the Bedrock console (*Inference profiles* → *Create*) and use that ARN as `model_arn`.

## Customization

**Swap the agent logic.** Edit `lambda/handler.py`. The Strands `Agent` is built once at module import (for container reuse) and reset per-invocation to avoid conversation-history bleed — see the module docstring if you want to change this behavior.

**Add more tools.** Define any function with the `@tool` decorator and include it in the `Agent(tools=[...])` list. Each tool call shows up as its own span in HoneyHive.

**Change the model.** Pass a different `model_arn` at deploy time:

```bash
npx --yes cdk deploy -c model_arn="arn:aws:bedrock:us-east-1:...:application-inference-profile/..."
```

**Point at self-hosted HoneyHive.**

```bash
npx --yes cdk deploy -c honeyhive_server_url=https://honeyhive.your-domain.com ...
```

**Use a custom secret name.** If you already manage HoneyHive creds in a differently-named secret:

```bash
npx --yes cdk deploy -c honeyhive_secret_name=team-x/honeyhive ...
```

**Route Bedrock traffic through LiteLLM.** Set `litellm_base_url` as context and the stack will inject `LITELLM_BASE_URL` into the Lambda environment. You'll need to update `lambda/handler.py` to honor it (the default wiring calls Bedrock directly).

## Cleanup

```bash
npx --yes cdk destroy
```

Optionally delete the HoneyHive secret (kept separate so you don't have to recreate it for each deploy):

```bash
aws secretsmanager delete-secret \
  --secret-id honeyhive/api-key \
  --force-delete-without-recovery
```

## Further reading

- [HoneyHive docs](https://docs.honeyhive.ai) — tracing model, sessions, evaluations.
- [Strands agents](https://strandsagents.com/latest/) — tool definitions, model providers, multi-agent patterns.
- [AWS Bedrock inference profiles](https://docs.aws.amazon.com/bedrock/latest/userguide/inference-profiles.html) — when you need an inference profile vs. foundation model vs. application inference profile.
- **AgentCore runtime variant** — an AWS AgentCore version of this cookbook is coming soon.

## Version pins

`lambda/requirements.txt` uses exact pins — reproducibility over flexibility. The HoneyHive SDK is pinned to `1.0.0rc21` because it's the earliest rc with both the session_id baggage isolation (prevents warm-Lambda session bleed across users) and the event_type priority detection that routes Strands GenAI ops (`invoke_agent` → chain, `execute_tool` → tool, `chat` → model) instead of falling through to the generic `tool` default. See the header of `lambda/requirements.txt` for the full rationale.
