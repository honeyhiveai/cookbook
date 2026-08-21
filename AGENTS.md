# AGENTS.md

## Cursor Cloud specific instructions

This repo is a monorepo of **independent HoneyHive integration cookbooks**. Each top-level
directory is a standalone example with its own README, its own dependency set, and (for Python)
its own virtual environment. There is no shared/root package, no test suite, and no lint config.
Always work inside the specific cookbook directory you care about.

### Toolchain / how deps are installed
- Python deps use **uv** (installed to `~/.local/bin`; `~/.bashrc` already adds it to PATH for
  interactive shells). In a non-interactive context use the absolute path `~/.local/bin/uv`.
- The startup update script creates a **per-cookbook `.venv`** for each Python cookbook and runs
  `pnpm install` for the one TypeScript cookbook. Do not create a single shared venv: the
  cookbooks pin conflicting dependency versions.
- Run a Python cookbook from inside its directory so `uv run` auto-detects its `.venv`, e.g.
  `cd openai-honeyhive-cookbook && uv run python basic_chat.py`. Standard run commands live in
  each cookbook's README.
- `honeyhive-skills-strands` is managed with `pyproject.toml` + `uv.lock` (use `uv sync`), not a
  plain `requirements.txt` venv.

### Credentials available in this environment (as secrets/env vars)
`HH_API_KEY`, `HH_API_URL`, `HH_PROJECT`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`, `ANTHROPIC_API_KEY`.
The HoneyHive SDK reads `HH_API_KEY` / `HH_API_URL` / `HH_PROJECT` from the environment, so no
`.env` file is needed for the runnable cookbooks below.

### What can actually be run end-to-end here
- `openai-honeyhive-cookbook` — needs HoneyHive + OpenAI. Runnable.
- `google-adk-cookbook` — needs HoneyHive + Google/Gemini. Runnable (`uv run python main.py --version v2`).
- `honeyhive-skills-strands` — needs HoneyHive + OpenAI. Runnable (`uv run python agent.py "..."`).

### Blocked cookbooks (deps still install for editing, but they cannot run here)
- AWS Bedrock creds missing: `aws-bedrock-honeyhive-cookbook`, `claims-summarizer-python`,
  `strands-agentcore-cookbook` (also needs the AgentCore runtime/CLI + AWS infra).
- Azure OpenAI deployment missing: `azure-openai-honeyhive-cookbook`,
  `legacy_cookbooks/claims-transcript-summarizer-js`.
- `cursor-sdk-honeyhive` (TypeScript): needs `CURSOR_API_KEY` at runtime. `pnpm build` and
  `pnpm typecheck` still work without it.
- `qdrant-cookbook`: creds are covered (HoneyHive + OpenAI) but it expects a **live Qdrant server**
  at `QDRANT_URL` (default `http://localhost:6333`); start one (e.g. Docker) or switch the client
  to in-memory mode before running.
- `wealth-management-agent`: **excluded from the update script** because its pinned `crewai`
  requires `opentelemetry-sdk<1.35` while `honeyhive>=1.0.0` requires `>=1.41.0`, so its
  `requirements.txt` is currently unresolvable (independent of the also-missing `SERPAPI_KEY`).

### Non-obvious gotchas
- `google-adk-cookbook/main.py` prints a benign `Failed to detach context` OpenTelemetry
  traceback on stderr during async teardown. It is harmless: the process exits 0 and the full
  agent response + `Session ID` are printed. Do not try to "fix" it.
- To confirm traces actually reached HoneyHive, query by the printed session id:
  `hh.events.get_by_session_id(session_id, project=os.getenv("HH_PROJECT"))` using
  `from honeyhive import HoneyHive` (constructed with `api_key=` and `server_url=`).
