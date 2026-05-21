# No HoneyHive — Strands baseline

Pure Strands + OpenAI. **No HoneyHive code, no eval harness** — just `agent.py`.

Use this folder for Steps 1–2 of the skill walkthrough (run baseline → instrument). For evals and a reference integration, use [`config-as-code/`](../config-as-code/).

Open **`no-honeyhive/`** in your coding agent so nothing HoneyHive-related is in the tree until the instrument skill adds it.

## What you need

- [OpenAI API key](https://platform.openai.com/api-keys) → `OPENAI_API_KEY` in `.env`
- [HoneyHive API key](https://app.us.honeyhive.ai/settings/project/keys) → add `HH_API_KEY` to `.env` before Step 2

## Setup

From the repo root, install HoneyHive skills once:

```bash
git clone https://github.com/honeyhiveai/cookbook.git
cd cookbook/honeyhive-skills-strands
npx skills add honeyhiveai/skills --skill '*'
```

Then work in this folder:

```bash
cd no-honeyhive
cp .env.example .env   # fill in OPENAI_API_KEY
uv sync
```

Open **`no-honeyhive/`** in your coding agent and start a **new** chat.

---

## Step 1 — Baseline

```text
Set up and run agent.py here. Use uv if available.
```

```bash
uv run python agent.py "What is 17 * 23?"
```

---

## Step 2 — Instrument

Have your HoneyHive key ready to paste when asked.

```text
Instrument this project with HoneyHive.
```

Check traces in [HoneyHive Studio](https://app.us.honeyhive.ai/traces/sessions).

---

## Steps 3–4 — Evaluate & improve

This folder stays minimal on purpose. For evals and a full reference stack, switch to [`config-as-code/`](../config-as-code/) — or ask the **evaluate** / **improve** skills here after Step 2 and let them add what you need.

---

## Stuck?

```text
I'm stuck on honeyhive-skills-strands/no-honeyhive. Read README.md, check OPENAI_API_KEY in .env, and fix.
```
