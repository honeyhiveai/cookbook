# HoneyHive Skills + Strands

Two self-contained Strands + OpenAI cookbooks for learning HoneyHive skills without cross-contamination.

| Folder | Purpose |
|--------|---------|
| [`no-honeyhive/`](no-honeyhive/) | Baseline agent — walk through **instrument → evaluate → improve** skills from scratch |
| [`honeyhive-integrated/`](honeyhive-integrated/) | Reference implementation with tracing + eval harness already wired |

Each folder has its own `agent.py`, `evaluate.py`, `README.md`, and dependencies. Open the folder you're working in as your agent workspace root.

## Setup (once)

```bash
git clone https://github.com/honeyhiveai/cookbook.git
cd cookbook/honeyhive-skills-strands
npx skills add honeyhiveai/skills --skill '*'
```

The CLI is interactive — choose which coding agent to install into. Skills install at this level and apply when you open either subfolder.

## Which folder?

- **Learning the skills?** → open [`no-honeyhive/`](no-honeyhive/) and follow its README.
- **Running evals against a known-good integration?** → open [`honeyhive-integrated/`](honeyhive-integrated/) and follow its README.

## Stuck?

```text
I'm stuck on honeyhive-skills-strands. Read the README in the folder I'm working in, check OPENAI_API_KEY and HH_API_KEY in .env, and fix.
```

Re-run `npx skills add honeyhiveai/skills --skill '*'`, pick your agent, then **start a new chat** in the subfolder you're using.
