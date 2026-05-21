# HoneyHive config as code — Strands reference

Strands + OpenAI agent **pre-wired with HoneyHive tracing** and an eval harness driven by [config as code](https://docs.honeyhive.ai/v2/sdk-reference/cli-config-as-code): datasets, datapoints, and evaluators live under `.honeyhive/` and sync to HoneyHive with the CLI.

Open **this folder** (`config-as-code/`) in your coding agent when working on evals or improvements.

## What you need

- [OpenAI API key](https://platform.openai.com/api-keys) → `OPENAI_API_KEY` in `.env`
- [HoneyHive API key](https://app.us.honeyhive.ai/settings/project/keys) → `HH_API_KEY` in `.env`
- [HoneyHive CLI](https://docs.honeyhive.ai/v2/sdk-reference/cli) (optional, for syncing `.honeyhive/` to your project)

## Setup

From the repo root, install HoneyHive skills once:

```bash
git clone https://github.com/honeyhiveai/cookbook.git
cd cookbook/honeyhive-skills-strands
npx skills add honeyhiveai/skills --skill '*'
```

Then work in this folder:

```bash
cd config-as-code
cp .env.example .env   # fill in keys
uv sync
```

Open **`config-as-code/`** in your coding agent and start a **new** chat.

---

## Config as code layout

```
.honeyhive/
├── datasets/strands-skills-eval.yaml
├── datapoints/          # one YAML per test case
├── evaluators/          # server-side evaluator definitions (CLI sync)
└── state.json           # IDs after first sync (commit after bootstrap)
```

Edit datapoints or evaluators in YAML, then push to HoneyHive:

```bash
bash sync-honeyhive.sh
```

`evaluate.py` loads datapoints from `.honeyhive/datapoints/` and runs client-side evaluators (`answer_correct`, `task_quality`) via `evaluate()`. The LLM judge in `.honeyhive/evaluators/task-quality.yaml` mirrors the offline judge for server-side use after sync.

---

## Run the agent

```bash
uv run python agent.py "What is 17 * 23?"
```

Check traces in [HoneyHive Studio](https://app.us.honeyhive.ai/traces/sessions).

---

## Run the eval

```bash
uv run python evaluate.py
```

Or ask your agent:

```text
Evaluate agent.py with HoneyHive.
```

---

## Improve (optional)

```text
Improve this agent using HoneyHive traces.
```

---

## Stuck?

```text
I'm stuck on honeyhive-skills-strands/config-as-code. Read README.md, check OPENAI_API_KEY and HH_API_KEY in .env, and fix.
```
