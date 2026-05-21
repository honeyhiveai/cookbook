---
name: honeyhive-evaluate
description: >
  Set up and verify HoneyHive experiments for an AI agent or LLM workflow. Use
  when the user wants to evaluate an agent, run an experiment, create or reuse a
  dataset, add evaluators or rubrics, compare experiment runs, or wire
  `evaluate()` with HoneyHive. Triggers on phrases like "evaluate my agent",
  "run an experiment", "create an eval dataset", "add evaluators", "compare
  runs", `honeyhive experiments`, `honeyhive datasets`, or `evaluate()`.
license: MIT
metadata:
  version: "0.1.0"
  homepage: https://docs.honeyhive.ai
---

# HoneyHive Evaluate

Set up the smallest useful HoneyHive experiment for the user's AI workflow: identify the target, shape or reuse a dataset, choose a compact evaluator set, run the experiment, and verify the results can be compared.

## Relevant v2 Docs

When you need product or API documentation, prefer these v2 docs:

- [Experiments Quickstart](https://docs.honeyhive.ai/v2/introduction/experiments-quickstart.md) for the smallest end-to-end experiment setup
- [Evaluation Introduction](https://docs.honeyhive.ai/v2/evaluation/introduction.md) for the experiments mental model
- [Comparing Experiments](https://docs.honeyhive.ai/v2/evaluation/comparing_evals.md) for regression and baseline workflows
- [Experiments via API](https://docs.honeyhive.ai/v2/evaluation/via-api.md) for non-Python or custom orchestration paths
- [Datasets Introduction](https://docs.honeyhive.ai/v2/datasets/introduction.md) and [Curate from Traces](https://docs.honeyhive.ai/v2/datasets/dataset-curation.md) for dataset reuse and creation
- [Evaluators Introduction](https://docs.honeyhive.ai/v2/evaluators/introduction.md), [Python Evaluators](https://docs.honeyhive.ai/v2/evaluators/python.md), [LLM Evaluators](https://docs.honeyhive.ai/v2/evaluators/llm.md), and [Evaluator Template List](https://docs.honeyhive.ai/v2/evaluators/evaluator-templates.md) for evaluator design
- [HoneyHive CLI](https://docs.honeyhive.ai/v2/sdk-reference/cli.md), [SDK Overview](https://docs.honeyhive.ai/v2/sdk-reference/overview.md), [Python SDK](https://docs.honeyhive.ai/v2/sdk-reference/python-sdk-ref.md), and [TypeScript SDK](https://docs.honeyhive.ai/v2/sdk-reference/typescript-sdk-ref.md) for concrete v2 SDK and CLI surfaces

## Phase 0 - Ask Before Acting

Before changing code, dependencies, datasets, datapoints, experiment runs, or evaluators, understand the user's goal and get alignment. Prefer asking at most 2-4 targeted questions at once.

Clarify:

- **Target:** Which agent, function, route, notebook, or job should be evaluated? In a monorepo, identify the exact subtree before proceeding.
- **Evaluation goal:** What regression or quality question should the experiment answer (accuracy, groundedness, tool-use success, safety, latency, cost, formatting, etc.)?
- **Mode:** Is this an offline batch experiment, online production evaluation, or a comparison between two existing runs?
- **HoneyHive state:** Does the user have `HH_API_KEY` set? Do they need `HH_API_URL` for a dedicated or self-hosted deployment? Only ask about an explicit project override if the user wants a non-default project target or label.
- **Resources:** Should the skill reuse existing datasets/evaluators/runs, or is it allowed to create new ones?
- **Edit tolerance:** Is the user okay with code changes, dependency changes, and local commands, or do they only want a plan?

If the target workflow or permission to mutate resources is ambiguous, stop and ask. Do not guess.

## Phase 1 - Read-Only Discovery

Run discovery before proposing any changes.

1. **Find the target workflow.** Search for agent entry points, LLM calls, RAG pipelines, tool loops, eval scripts, notebooks, routes, and tests. Scope all future edits to that subtree.
2. **Detect existing evaluation work.** Look for `evaluate(`, `run_experiment(`, `experiments/`, eval-oriented tests, rubric docs, golden datasets, CSV/JSON test cases, HoneyHive dataset IDs, run IDs, CI regression scripts, or manual review workflows.
3. **Inventory candidate data.** Identify existing examples from tests, logs, fixtures, user-provided files, HoneyHive datasets, or previous experiment runs.

Discovery is read-only. Codebase inspection and read-only HoneyHive CLI commands are both allowed here. It is fine to use `honeyhive --help`, `honeyhive <namespace> --help`, and non-mutating list/get commands during discovery. Do not create, update, or delete datasets, datapoints, metrics/evaluators, or experiment runs yet.

If the user is unsure what to measure, start from a small representative sample of examples and identify concrete failure modes before proposing evaluators. Review the full workflow when possible, not just the final output: user input, retrieved context or tool results, intermediate steps, and final output. Write observations, not theories, for example "missed the budget constraint" instead of "model was confused."

## Phase 2 - Choose the Path

Pick the smallest path that answers the user's evaluation question.

- **Not instrumented yet:** You can still propose an offline experiment around the intended target workflow and a dataset, even if the agent is only partially built. Explain that trace-rich debugging and production-event datasets may require `honeyhive-instrument` first. Do not force instrumentation unless the user agrees.
- **Already instrumented:** Reuse the existing tracing/session/event conventions. Do not add duplicate tracer or client setup.
- **Existing HoneyHive dataset:** Verify it with `honeyhive datasets list` and inspect datapoints with `honeyhive datapoints list` / `get` where useful. Reuse it if the shape matches the target function.
- **No dataset:** Propose a tiny seed dataset from existing examples, fixtures, logs, traces, or user-provided cases. Keep the first dataset small enough to review.
- **Evaluation-first, partially built workflow:** Define the intended behavior and success criteria first, then create a seed dataset that describes that target behavior. Do not assume traces or production events already exist.
- **Python target:** Use the Python SDK's experiment APIs (for example `evaluate()`) inside the user's evaluation harness. Use the HoneyHive CLI for HoneyHive resource CRUD and verification.
- **TypeScript or non-Python target:** Prefer the HoneyHive CLI for terminal or agent-driven HoneyHive resource workflows when it exposes the needed operation. The TypeScript SDK (`@honeyhive/api-client`) and generated OpenAPI clients are also valid documented options for non-Python codebases. Build the smallest local harness that calls the target workflow and records or links results. Do not pretend Python-only helpers exist in TypeScript.
- **CLI availability:** If `honeyhive` is not installed, ask the user before installing `@honeyhive/cli` or falling back to a non-CLI path.

## Phase 3 - Plan and Wait

Before mutating anything, present a concise plan and wait for the user's approval.

The plan should include:

- Target function or workflow and the repo subtree to edit.
- Dataset source and shape, including whether it reuses an existing HoneyHive dataset.
- Evaluator approach, including any metrics/evaluators to create or reuse.
- Files to edit and dependencies, if any.
- HoneyHive CLI commands that will create, update, or verify resources.
- Validation steps and what success looks like.

If the user rejects the plan or asks for a narrower scope, revise the plan before acting.

## Phase 4 - Apply the Minimal Harness

Use the HoneyHive CLI for HoneyHive API operations whenever the command exists.

Common namespaces may include:

- `honeyhive datasets`
- `honeyhive datapoints`
- `honeyhive experiments`
- `honeyhive metrics` for evaluator surfaces that are still exposed as metrics

The exact namespace set can vary by CLI version. Do not hardcode subcommands from memory when the CLI is available. Run `honeyhive --help` or `honeyhive <namespace> --help` to discover the exact command before using it.

Use SDK calls when they belong inside the user's code path or when the CLI does not expose the needed operation. For Python experiments, `evaluate()` is the preferred in-code orchestration API when it fits the target.

Keep the first implementation small:

1. Create or reuse one dataset.
2. Add a small, reviewable set of datapoints.
3. Add or reuse a compact evaluator set.
4. Wire the target workflow into the experiment harness.
5. Run the experiment only after the user has approved local command execution.

Evaluator guidance:

- Start with one or two high-impact evaluators, not a long list.
- Prefer narrow checks over holistic scores. "did the answer match ground truth?" is better than "was this response good overall?"
- Use code checks before LLM judges for objective criteria like schema conformance, exact-format checks, required fields, simple thresholds, or deterministic business rules.
- Prefer binary pass/fail decisions over 1-5 or letter grades when possible. They are easier to calibrate and compare across runs.

## Phase 5 - Validate

Validation must prove the experiment can be used for regression tracking, not just that a script ran.

Check:

1. **Resource visibility:** The dataset is visible in the datasets namespace, and datapoints are linked as expected.
2. **Run status:** The run is visible in the experiments namespace with a terminal or understandable status.
3. **Metrics/results:** Experiment results or evaluator output are retrievable through the experiments namespace when metrics are expected.
4. **Comparison:** If there is a baseline run, an experiments comparison command works programmatically.
5. **Local fit:** The harness calls the intended target workflow and does not require unrelated refactors.

If validation fails because the app is not instrumented, the dataset shape is wrong, CLI coverage is missing, the SDK version is incompatible, or docs are incomplete, stop with a clear explanation and the next recommended step.

## Gotchas

- **Prefer the CLI for terminal or agent-driven resource workflows.** Use the SDK inside the user's harness when it belongs there, but prefer `honeyhive` for datasets, datapoints, experiment runs, and metrics/evaluators whenever the needed command exists.
- **Evaluators may be called metrics.** Product language says "evaluators"; API and CLI surfaces may still say `metrics`. Bridge the naming for the user.
- **No metric sprawl.** Too many small metrics make an event hard to understand. Prefer a compact set.
- **No hidden resource creation.** Do not create datasets, datapoints, metrics, runs, or alerts until the user approves the plan.
- **No secret writes.** Read `HH_API_KEY` and any relevant environment settings such as `HH_API_URL` from the environment or ask the user to set them. Only ask for an explicit project override when the user needs one. Never write API keys to source files.
- **No forced instrumentation.** If the app is not instrumented, explain the tradeoff and offer an offline path or a handoff to `honeyhive-instrument`.
- **No version upgrades by default.** If the installed SDK or CLI is incompatible, surface the issue and ask before upgrading.
