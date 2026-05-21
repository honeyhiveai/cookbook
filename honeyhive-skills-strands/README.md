# HoneyHive Skills + Strands

Two self-contained Strands + OpenAI tracks.

| Folder | Purpose |
|--------|---------|
| [`no-honeyhive/`](no-honeyhive/) | Pure Strands — **`agent.py` only**. Walk through **instrument** skill (Steps 1–2). |
| [`honeyhive-integrated/`](honeyhive-integrated/) | Reference — tracing + **`evaluate.py`** harness. Run evals here. |

## Setup (once)

```bash
git clone https://github.com/honeyhiveai/cookbook.git
cd cookbook/honeyhive-skills-strands
npx skills add honeyhiveai/skills --skill '*'
```

The CLI is interactive — choose which coding agent to install into. Skills install at this level and apply when you open either subfolder.

## Which folder?

- **Learning instrument on a clean baseline?** → [`no-honeyhive/`](no-honeyhive/)
- **Running evals or checking a known-good integration?** → [`honeyhive-integrated/`](honeyhive-integrated/)

## Stuck?

```text
I'm stuck on honeyhive-skills-strands. Read the README in the folder I'm working in and fix.
```

Re-run `npx skills add honeyhiveai/skills --skill '*'`, pick your agent, then **start a new chat** in the subfolder you're using.
