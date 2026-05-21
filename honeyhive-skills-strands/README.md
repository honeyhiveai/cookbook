# HoneyHive Skills + Strands

Strands + OpenAI baseline (no HoneyHive in code yet).

## What you need

- [OpenAI API key](https://platform.openai.com/api-keys) → `OPENAI_API_KEY` in `.env`
- [HoneyHive API key](https://app.us.honeyhive.ai/settings/project/keys) → `HH_API_KEY` in `.env` (before instrumenting)

## Setup

```bash
git clone https://github.com/honeyhiveai/cookbook.git
cd cookbook/honeyhive-skills-strands
npx skills add honeyhiveai/skills --skill '*'
```

The CLI is interactive — choose which coding agent to install into. Then open this folder in **that** agent and start a **new** chat (skills load only in sessions started after install).

---

## Step 1 — Baseline

```text
Set up and run agent.py here. Use uv if available.
```

---

## Step 2 — Instrument

Have your HoneyHive key ready to paste when asked.

```text
Instrument this project with HoneyHive.
```

Check traces in [HoneyHive Studio](https://app.honeyhive.ai).

---

## Step 3 — Experiment (optional)

```text
Evaluate agent.py with HoneyHive.
```

---

## Step 4 — Improve (optional)

```text
Improve this agent using HoneyHive traces.
```

---

## Stuck?

```text
I'm stuck on honeyhive-skills-strands. Read README.md, check OPENAI_API_KEY and HH_API_KEY in .env, and fix.
```

Re-run `npx skills add honeyhiveai/skills --skill '*'`, pick your agent, then **start a new chat** in this folder.