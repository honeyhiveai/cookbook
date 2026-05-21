# No HoneyHive — Strands baseline

Strands + OpenAI agent with **no HoneyHive wiring in code**. Use this folder for the instrument → evaluate → improve skill walkthrough.

Open **this folder** (`no-honeyhive/`) in your coding agent so the baseline stays clean and separate from `honeyhive-integrated/`.

## What you need

- [OpenAI API key](https://platform.openai.com/api-keys) → `OPENAI_API_KEY` in `.env`
- [HoneyHive API key](https://app.us.honeyhive.ai/settings/project/keys) → `HH_API_KEY` in `.env` (before Step 2)

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
cp .env.example .env   # fill in keys
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

## Step 3 — Experiment

```text
Evaluate agent.py with HoneyHive.
```

```bash
uv run python evaluate.py
```

---

## Step 4 — Improve

```text
Improve this agent using HoneyHive traces.
```

---

## Stuck?

```text
I'm stuck on honeyhive-skills-strands/no-honeyhive. Read README.md, check OPENAI_API_KEY and HH_API_KEY in .env, and fix.
```
