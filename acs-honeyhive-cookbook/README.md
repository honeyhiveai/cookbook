# HoneyHive observability for Microsoft's Agent Control Specification (ACS)

Govern a HoneyHive-traced agent with **Microsoft's [Agent Control Specification
(ACS)](https://github.com/microsoft/agent-governance-toolkit)** and emit **every
ACS runtime decision as a HoneyHive span**, so policy enforcement
(`allow` / `deny` / `escalate` / `transform` / `warn`) shows up inline in the
same trace as the agent's model and tool calls.

This is the runtime-governance half of Microsoft's "open trust stack":

```
evaluate (ASSERT)  ->  enforce (ACS)  ->  observe (HoneyHive)
```

ACS is the **runtime-enforcement standard**: at each agent boundary the host
hands ACS a JSON snapshot of what is about to happen, ACS evaluates the bound
policy and returns a verdict, and the host enforces it. This cookbook adds the
third leg — turning each ACS verdict into a queryable HoneyHive span over
OpenInference / OTLP — so governance is observable alongside the rest of the
agent trace. HoneyHive is a listed ACS partner.

> **ACS is `v0.3.1-beta`.** Its APIs and manifest schema may change before GA.
> Pin versions and expect churn. For authoritative manifest/Rego authoring, see
> ACS's own
> [`policy-engine/QUICKSTART.md`](https://github.com/microsoft/agent-governance-toolkit/blob/main/policy-engine/QUICKSTART.md).

## What this cookbook runs

It drives Microsoft's **official `bank_agent` example** (its real Rego policy and
manifest, banking domain) through all 8 ACS intervention points against the
**real ACS runtime** (`AgentControl.from_path(...)` + OPA), not the bundled
stdlib mock demo. Each evaluation is captured as a HoneyHive span.

### Decision coverage (verified end to end)

| Intervention point | Decision    | Trigger                                                        |
|--------------------|-------------|---------------------------------------------------------------|
| `agent_startup`    | `allow`     | —                                                             |
| `input`            | `deny`      | `annotations.prompt_classifier.risk_score >= 0.95`            |
| `pre_model_call`   | `transform` | appends a "no high-value transfers" system reminder           |
| `post_model_call`  | `deny`      | model response contains "bypass approval"                     |
| `pre_tool_call`    | `escalate`  | `wire_transfer` with `amount >= 10000`                        |
| `post_tool_call`   | `transform` | redacts `account_id` -> `ACCOUNT-REDACTED`                    |
| `output`           | `transform` | regex-redacts `CHK-[0-9]+` -> `ACCOUNT-REDACTED`              |
| `agent_shutdown`   | `warn`      | shutdown summary has blocked actions                          |

The `input` and `pre_model_call` rules read derived classifier annotations. In
production those come from `classifier` annotator *endpoints*; here a small
**offline annotator dispatcher** (`bank_agent/annotators.py`) returns
deterministic classifier values so all 8 points fire with **zero network calls**.

## Layout

```
acs-honeyhive-cookbook/
├── acs_honeyhive.py        # the bridge: instrument_acs() + manual make_acs_guard()
├── bank_agent_runner.py    # drives the bank_agent through all 8 ACS points
├── verify_honeyhive.py     # queries the HoneyHive events API and asserts coverage
├── minimal_smoke.py        # zero-config sanity check (manual wrapper)
├── bank_agent/
│   ├── manifest.yaml       # reused from the official bank_agent (custom annotator)
│   ├── policy/bank_agent_rego.rego   # the REAL upstream policy, verbatim
│   ├── annotators.py       # offline classifier annotator dispatcher
│   └── snapshots/*.json    # one host snapshot per intervention point
├── minimal/                # annotator-free manifest + Rego to sanity-check wiring
│   ├── manifest.yaml
│   └── policy/guardrails.rego
├── scripts/setup_opa.sh    # download the OPA binary and print ACS_OPA_PATH
├── requirements.txt
└── .env.example
```

## Prerequisites

- **Python 3.11+**
- A **HoneyHive** API key, and optionally an **OpenAI** API key (for a real
  inline model-call span).
- The **OPA binary** on disk. ACS uses OPA to evaluate Rego policies and **fails
  closed** without it.

## Setup

Use [`uv`](https://docs.astral.sh/uv/):

```bash
git clone https://github.com/honeyhiveai/cookbook.git
cd cookbook/acs-honeyhive-cookbook
uv venv --python 3.11
source .venv/bin/activate
uv pip install -r requirements.txt
```

### OPA setup note

ACS needs the `opa` binary to evaluate Rego. Download the static build and point
`ACS_OPA_PATH` at it:

```bash
./scripts/setup_opa.sh
export ACS_OPA_PATH="$PWD/bin/opa"
```

`scripts/setup_opa.sh` picks the right asset for your platform (e.g.
`opa_linux_amd64_static` in cloud, `opa_darwin_arm64_static` on Apple Silicon),
`chmod +x`'s it, and prints the path. `$ACS_OPA_PATH` is authoritative when set;
a bad explicit path fails closed instead of falling back to another `opa` on
`PATH`.

### Credentials

Copy `.env.example` to `.env` and fill it in (or export the variables):

```bash
HH_API_KEY=...              # HoneyHive
OPENAI_API_KEY=...          # optional
ACS_OPA_PATH=/abs/path/opa  # required for Rego
# HH_API_URL=...            # optional, non-default region
# HH_PROJECT=...            # optional, for the verification query
```

## Run it

```bash
# 1) (optional) sanity-check ACS + OPA + HoneyHive wiring with the minimal policy
python minimal_smoke.py

# 2) govern the bank_agent through all 8 ACS points; emit a span per decision
python bank_agent_runner.py

# 3) confirm the spans landed in HoneyHive
python verify_honeyhive.py
```

`bank_agent_runner.py` prints a per-point summary and reports the HoneyHive
`source` and `session_name` so the trace is easy to find:

```
agent_startup    -> allow     | proceed (allowed)
input            -> deny      | BLOCKED [input_classifier_high_risk]: ...
pre_model_call   -> transform | proceed with transformed policy target: ...
post_model_call  -> deny      | BLOCKED [model_suggested_approval_bypass]: ...
pre_tool_call    -> escalate  | SUSPENDED [large_wire_transfer_requires_review] -> approval denied: ...
post_tool_call   -> transform | proceed with transformed policy target: {'account_id': 'ACCOUNT-REDACTED', ...}
output           -> transform | proceed with transformed policy target: {'text': '... ACCOUNT-REDACTED ...'}
agent_shutdown   -> warn      | proceed, warning recorded: ...
Decision types observed: allow, deny, escalate, transform, warn
```

Find the trace in HoneyHive by `source='acs-bank-demo'` and
`session_name='acs-bank-agent'`. The ACS `acs.guard` spans, the agent's
`agent.model_call` / OpenInference `ChatCompletion` span, and the
`governed_bank_turn` parent all share one session.

## The bridge

Every ACS guard helper in the Python SDK — `run`, `run_tool`, `protect_tool`,
`enforce`, the lifecycle seams, and the `guard_*` framework adapters — funnels
through one method:

```python
AgentControl.evaluate_intervention_point(intervention_point, snapshot, mode)
```

`acs_honeyhive.py` offers two surfaces over it.

### Easy mode (recommended): `instrument_acs()`

Monkeypatches `evaluate_intervention_point` so **all** ACS activity is captured
as HoneyHive spans with **zero changes** to agent/host code:

```python
from honeyhive import HoneyHiveTracer
from openinference.instrumentation.openai import OpenAIInstrumentor
from agent_control_specification import AgentControl
from acs_honeyhive import instrument_acs

tracer = HoneyHiveTracer.init(api_key=..., source="acs-bank-demo", session_name="acs-bank-agent")
OpenAIInstrumentor().instrument(tracer_provider=tracer.provider)

instrument_acs(tracer)                       # <- the one line

control = AgentControl.from_path("bank_agent/manifest.yaml", annotator_dispatcher=...)
result = await control.evaluate_intervention_point(intervention_point, snapshot)
# ^ now automatically emits a HoneyHive span with the decision detail
```

Each span carries, as queryable HoneyHive fields:

- **metadata**: `acs.intervention_point`, `acs.decision`, `acs.reason`,
  `acs.message`, `acs.input_identity`, `acs.enforced_identity`
- **metrics**: `acs_allowed`, `acs_warned`, `acs_denied`, `acs_escalated`,
  `acs_transformed`
- **outputs**: `decision`, `reason`, `message`, `transformed_policy_target`

> `enrich_span` stores dotted metadata keys **nested**, so `acs.decision` is read
> back as `metadata["acs"]["decision"]` in the events API. `verify_honeyhive.py`
> accounts for this.

### For understanding: `make_acs_guard()`

The explicit one-evaluation-to-one-span wrapper (used by `minimal_smoke.py`):

```python
from acs_honeyhive import make_acs_guard

acs_guard = make_acs_guard(control)
result = await acs_guard(intervention_point, snapshot)
```

## Acting on verdicts (host obligations)

ACS decides, the host enforces. `bank_agent_runner.py` applies the
spec-prescribed host action for each decision:

| Decision    | Host action                                           |
|-------------|-------------------------------------------------------|
| `allow`     | proceed unchanged                                     |
| `warn`      | proceed, record the warning                           |
| `deny`      | block; surface `reason` + `message`                   |
| `escalate`  | suspend; consult an approval path (stub rejects)      |
| `transform` | proceed only with `result.transformed_policy_target`  |

For a clear demonstration the runner evaluates every point in sequence and logs
the host action it *would* take, rather than halting on the first `deny`.

## Gotchas worth knowing

- **Run the real runtime, not the mock.** Upstream `demo/run_demo.py` is a
  stdlib re-implementation of the policy; it does not run Rego. This cookbook
  uses `AgentControl.from_path(...)` against the real `bank_agent_rego.rego`.
- **`transform` path rooting.** A `transform` verdict's `path` is rooted at the
  raw selected policy-target value. Use `"$policy_target"` for a bare string, or
  `"$policy_target.<member>"` for an object member (the bank_agent Rego already
  uses correct paths like `$policy_target.messages`, `$policy_target.account_id`,
  `$policy_target.text`). A wrong root yields `runtime_error:transform_invalid`.
- **HoneyHive flush.** Call `HoneyHiveTracer.flush_all()` at the end (the
  module-level `flush()` requires a tracer argument; `flush_all()` does not).

## Additional resources

- [Microsoft Agent Governance Toolkit (ACS)](https://github.com/microsoft/agent-governance-toolkit)
- [ACS QUICKSTART](https://github.com/microsoft/agent-governance-toolkit/blob/main/policy-engine/QUICKSTART.md)
- [ACS SDK surfaces](https://github.com/microsoft/agent-governance-toolkit/blob/main/policy-engine/docs/sdk-surfaces.md)
- [HoneyHive Documentation](https://docs.honeyhive.ai/)
