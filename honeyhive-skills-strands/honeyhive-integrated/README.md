# HoneyHive integrated — Strands reference

Strands + OpenAI agent **pre-wired with HoneyHive tracing** and a full eval harness. Use this folder to run experiments and compare against your instrumented baseline without cross-contamination.

Open **this folder** (`honeyhive-integrated/`) in your coding agent when working on evals or improvements.

## What you need

- [OpenAI API key](https://platform.openai.com/api-keys) → `OPENAI_API_KEY` in `.env`
- [HoneyHive API key](https://app.us.honeyhive.ai/settings/project/keys) → `HH_API_KEY` in `.env`

## Setup

From the repo root, install HoneyHive skills once:

```bash
git clone https://github.com/honeyhiveai/cookbook.git
cd cookbook/honeyhive-skills-strands
npx skills add honeyhiveai/skills --skill '*'
```

Then work in this folder:

```bash
cd honeyhive-integrated
cp .env.example .env   # fill in keys
uv sync
```

Open **`honeyhive-integrated/`** in your coding agent and start a **new** chat.

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
I'm stuck on honeyhive-skills-strands/honeyhive-integrated. Read README.md, check OPENAI_API_KEY and HH_API_KEY in .env, and fix.
```
