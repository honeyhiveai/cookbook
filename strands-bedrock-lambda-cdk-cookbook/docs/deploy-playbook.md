# Deploy playbook

End-to-end runbook for taking the `strands-bedrock-lambda-cdk-cookbook` stack from a clean checkout to a live API URL, three verified HoneyHive traces, and a clean teardown. This is the script the NW accelerator demo (and HHAI-4973 dry run) follows.

The README covers the user-facing flow. This playbook adds the ops-side detail: profile pre-checks, expected outputs at each step, fallback screenshot checklist, and rollback paths. Read this before running the demo live.

## Prerequisites

- **AWS profile for a HoneyHive-owned sandbox account.** Do *not* point this at a customer account (never at NW's), and do not reuse a control-plane / production HoneyHive profile. If you are unsure which profile on the demo machine is the sandbox, ask in #hackathon-accelerator before proceeding — wrong account = accidental provisioning.
- **Region: `us-east-1`.** This matches Nationwide's region and maximizes Bedrock model availability. If you must use a different region, swap it everywhere below (bootstrap, Secrets Manager, inference profile ARN, list-inference-profiles).
- **Python 3.12** available as `python3.12` on `$PATH`. Lambda runtime is pinned to 3.12 — mismatched local Python will produce native-wheel surprises during Docker bundling.
- **Node.js 18+** for the CDK CLI (`npx --yes cdk ...`).
- **Docker Desktop running.** `cdk deploy` uses the official `public.ecr.aws/sam/build-python3.12` image to bundle Lambda dependencies. If Docker is not up, synth/deploy fails with `docker exited with status 125`.
- **HoneyHive project + API key.** Project name must match `HONEYHIVE_PROJECT` at deploy time; a typo produces a silent trace drop.
- **Bedrock model access.** In the Bedrock console → *Model access*, grant access to the model family you intend to use (Claude 4.5 Sonnet for this demo). Access grants are region-scoped.

## Quick pre-flight

Before doing anything destructive, confirm you're pointed at the right account:

```bash
export AWS_PROFILE=<SANDBOX_PROFILE>
aws sts get-caller-identity
# Expect: Account = HoneyHive sandbox account ID. Arn contains the sandbox role name.
aws configure get region
# Expect: us-east-1
```

If the account ID doesn't match the known sandbox, stop. Do not proceed.

## Step-by-step

All commands run from `cookbook/strands-bedrock-lambda-cdk-cookbook/` unless otherwise noted.

### 1. Clone & enter

```bash
git clone https://github.com/honeyhiveai/cookbook.git
cd cookbook/strands-bedrock-lambda-cdk-cookbook
```

For this sub-issue, use the stacked branch:

```bash
git checkout hhai-4971-deploy-test
```

### 2. Install CDK synth deps

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Sanity check:

```bash
pip list | grep -E "aws-cdk-lib|constructs|boto3"
# Expect: aws-cdk-lib 2.248+ , constructs 10.5+ , boto3 1.34+
```

### 3. Ensure Docker is up

```bash
docker info | grep "Server Version"
# Expect: a version line, no "Cannot connect" errors.
```

If Docker is not running: `open -a Docker`, wait ~30s, retry.

### 4. Set AWS profile + region

```bash
export AWS_PROFILE=<SANDBOX_PROFILE>
export AWS_REGION=us-east-1
aws sts get-caller-identity   # confirm account
```

### 5. Create the HoneyHive API key secret

The stack reads via CloudFormation dynamic reference — the plaintext key never lands in the synthesized template.

```bash
export HONEYHIVE_API_KEY="hh-..."
aws secretsmanager create-secret \
  --name honeyhive/api-key \
  --secret-string "$HONEYHIVE_API_KEY" \
  --region us-east-1
```

If the secret already exists:

```bash
aws secretsmanager put-secret-value \
  --secret-id honeyhive/api-key \
  --secret-string "$HONEYHIVE_API_KEY" \
  --region us-east-1
```

### 6. Pick a model ARN

For Claude 4.5 Sonnet and any chargeback-tagged workload, use an **application-inference-profile** ARN. List profiles in the sandbox:

```bash
aws bedrock list-inference-profiles --region us-east-1 \
  --query 'inferenceProfileSummaries[].{name:inferenceProfileName, arn:inferenceProfileArn, type:type}' \
  --output table
```

Export the one you want:

```bash
export MODEL_ARN="arn:aws:bedrock:us-east-1:<ACCOUNT_ID>:application-inference-profile/<PROFILE_ID>"
```

If no application inference profile exists yet, create one in the Bedrock console (*Inference profiles* → *Create application inference profile*) against a Claude 4.5 Sonnet system-defined profile. Tag it `hackathon=accelerator` for chargeback visibility.

### 7. Bootstrap CDK (first time per account/region)

```bash
npx --yes cdk bootstrap aws://<ACCOUNT_ID>/us-east-1
```

Successful output ends with `✅  Environment aws://<ACCOUNT_ID>/us-east-1 bootstrapped`. Re-running is a no-op.

### 8. Synth (optional sanity check)

```bash
npx --yes cdk synth --quiet \
  -c honeyhive_project=<YOUR_PROJECT> \
  -c model_arn="$MODEL_ARN"
```

Synth requires Docker (it runs the Lambda bundling step). If it completes without error, the template is valid.

### 9. Diff against the deployed stack

```bash
npx --yes cdk diff \
  -c honeyhive_project=<YOUR_PROJECT> \
  -c model_arn="$MODEL_ARN"
```

On a clean account this shows only additions: Lambda function, IAM role + inline policy, HTTP API + route + integration, LogGroup, Secrets Manager reference. Review the IAM policy statements before proceeding — specifically the `bedrock:Invoke*` resource list should include `application-inference-profile/*`.

### 10. Deploy

```bash
npx --yes cdk deploy \
  -c honeyhive_project=<YOUR_PROJECT> \
  -c model_arn="$MODEL_ARN"
```

Expected duration: 2–4 minutes. CDK prints three outputs when done:

```
StrandsBedrockLambdaStack.ApiUrl = https://xxxxxxxxxx.execute-api.us-east-1.amazonaws.com
StrandsBedrockLambdaStack.LambdaArn = arn:aws:lambda:us-east-1:...:function:...
StrandsBedrockLambdaStack.RoleArn = arn:aws:iam::...:role/...
```

Capture the full terminal output for `fallback/01-cdk-deploy-output.png`.

```bash
export API_URL="<ApiUrl output>"
```

### 11. Invoke 3× back-to-back

```bash
for i in 1 2 3; do
  echo "--- invocation $i ---"
  curl -sS -X POST "$API_URL/invoke" \
    -H 'content-type: application/json' \
    -d "{\"prompt\": \"invocation $i: what is $((i*17)) * $((i*23))?\"}"
  echo
done
```

Each response has `response`, `session_url`, and `session_id`. Capture this output for `fallback/02-curl-response.png`.

### 12. Verify in HoneyHive Studio

- Open `session_url` from any one response, OR go to `app.honeyhive.ai/<project>/sessions` and filter "last 5 min".
- Confirm 3 distinct session_ids (no duplicates = baggage isolation working).
- Open one session. Expand spans. Expected hierarchy:
  - Top-level session span (`lambda-<hex>`)
  - `invoke_agent` → shows as **chain**
  - `chat` → shows as **model** (Bedrock Converse call, with prompt/completion + token counts)
  - `execute_tool` → shows as **tool** (the `calculator` span)
- Latency target: trace visible in Studio within 15s of the curl completing.

Capture:
- `fallback/03-studio-session-list.png` — filtered session list showing 3 distinct sessions.
- `fallback/04-studio-trace-spans.png` — one session expanded with agent/model/tool spans visible.

### 13. Teardown

```bash
npx --yes cdk destroy
# Type "y" to confirm.
```

Capture clean destroy output for `fallback/05-cdk-destroy.png`.

Optionally clean up the HoneyHive secret:

```bash
aws secretsmanager delete-secret \
  --secret-id honeyhive/api-key \
  --force-delete-without-recovery \
  --region us-east-1
```

## Verification checklist

- [ ] `cdk deploy` exits 0 with 3 outputs printed (ApiUrl, LambdaArn, RoleArn)
- [ ] `curl $API_URL/invoke` returns HTTP 200 with JSON containing `response`, `session_url`, `session_id`
- [ ] 3 back-to-back curls return 3 **distinct** `session_id`s (baggage session isolation working)
- [ ] HoneyHive Studio shows all 3 sessions within 15s of curl
- [ ] Each session's spans are classified as `chain` / `model` / `tool` — **not** all fall through to `tool` (event_type priority detection working)
- [ ] `cdk destroy` exits 0. Confirm in CloudFormation console that stack status is `DELETE_COMPLETE` and no resources remain in Lambda, IAM, API Gateway, or CloudWatch Logs.

## Screenshot checklist (Phase B fallback artifacts)

Stored under `docs/fallback/`.

| # | File | What it shows |
|---|------|---------------|
| 00 | `00-cdk-synth.txt` | Text output of `cdk synth --quiet` (archived for Phase A verification) |
| 00 | `00-cdk-diff.txt` | Text output of `cdk diff` against empty env (Phase A) |
| 01 | `01-cdk-deploy-output.png` | Terminal during/after `cdk deploy`, ApiUrl visible |
| 02 | `02-curl-response.png` | Terminal showing 3 curls + responses with distinct session_urls |
| 03 | `03-studio-session-list.png` | HoneyHive Studio session list filtered to last 5 min, 3 rows |
| 04 | `04-studio-trace-spans.png` | Single session expanded, agent/model/tool spans visible |
| 05 | `05-cdk-destroy.png` | Terminal after clean `cdk destroy`, 0 errors |

If any of these can't be captured live during the demo, use the stored fallback to walk the audience through the expected output.

## Rollback & common failure modes

**`docker exited with status 125` during synth/deploy.**
Docker Desktop is not running. Start it (`open -a Docker`), wait ~30s, retry.

**`ValidationException: ... on-demand throughput isn't supported`.**
`MODEL_ARN` points at a foundation-model ARN for a model that requires an inference profile (Claude 4.5, Nova). Switch to an `application-inference-profile/*` ARN. See step 6.

**`AccessDeniedException` on `bedrock:InvokeModel`.**
Either (a) model access not granted for your chosen model in the region (fix in Bedrock console), or (b) IAM policy missing the `application-inference-profile/*` resource pattern (check `stacks/strands_bedrock_lambda_stack.py`; default stack already includes it).

**Deploy succeeds; curl returns HTTP 500 with `"cold-start init failed"`.**
Lambda init raised. Cold-start guard returns structured 500. Check `/aws/lambda/<fn>` CloudWatch log group for the underlying error — most likely `HONEYHIVE_API_KEY` secret not in this region, or `HONEYHIVE_PROJECT` env missing.

**Curl succeeds but no trace in Studio.**
1. Confirm the secret exists in the deploy region: `aws secretsmanager get-secret-value --secret-id honeyhive/api-key --region us-east-1`.
2. Confirm `HONEYHIVE_PROJECT` value matches an actual project in your workspace (typos silently drop).
3. For self-hosted HoneyHive, pass `-c honeyhive_server_url=https://your-host` at deploy.

**Spans all classified as `tool` in Studio.**
HoneyHive SDK too old. Confirm `lambda/requirements.txt` is pinned to `honeyhive==1.0.0rc21` or newer; this rc adds the event_type priority detection that maps Strands GenAI ops correctly. Redeploy after updating.

**Session IDs bleed across invocations.**
SDK too old. Same pin fix as above — `rc10+` ships the baggage-based session isolation.

**`cdk destroy` leaves orphan resources.**
Check:
- CloudWatch log group (`/aws/lambda/<fn>`) — stack uses `RemovalPolicy.DESTROY`, so this should be gone. If not, delete manually.
- Secrets Manager secret — intentionally NOT owned by the stack; delete separately (step 13).
- Bedrock application inference profile — NOT created by the stack. Delete from the Bedrock console only if you created it for this demo.

## After the deploy test

- Post results (success or failures) as a Linear comment on [HHAI-4971](https://linear.app/honeyhive/issue/HHAI-4971).
- Any new friction discovered → open a follow-up on the README (HHAI-4969) to harden the *Common errors* section.
- When HHAI-4973 dry-runs this playbook, they should be able to reproduce the outputs step-for-step. If any step diverges, that's a playbook bug — fix here, not in the dry-run notes.
