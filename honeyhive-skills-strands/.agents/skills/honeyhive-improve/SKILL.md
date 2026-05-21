---
name: honeyhive-improve
description: >
  Debug and improve an AI agent or LLM workflow using HoneyHive trace data.
  Use when the user has a failing session, event, evaluator, experiment run,
  alert, or vague production complaint and wants root-cause analysis, a minimal
  fix plan, or a verified improvement loop. Triggers on phrases like "debug this
  trace", "investigate a failing session", "why did this run fail", "root cause",
  "production issue", `honeyhive events search`, `honeyhive experiments`, or
  evaluator failure analysis.
license: MIT
metadata:
  version: "0.1.0"
  homepage: https://docs.honeyhive.ai
  feedback_url: https://github.com/honeyhiveai/skills/issues
---

# HoneyHive Improve

Debug the failing part of the user's AI workflow with evidence first. Start from HoneyHive data when it exists, ask before mutating anything, propose the smallest evidence-backed fix, validate it, and stop.

## Relevant v2 Docs

When you need product or API documentation, prefer these v2 docs:

- [Tracing Introduction](https://docs.honeyhive.ai/v2/tracing/introduction.md) and [Tracing Concepts](https://docs.honeyhive.ai/v2/tracing/concepts.md) for the trace data model
- [Explore in UI](https://docs.honeyhive.ai/v2/tracing/ui-flows.md), [Tree View](https://docs.honeyhive.ai/v2/tracing/tree-view.md), and [Thread View](https://docs.honeyhive.ai/v2/tracing/thread-view.md) for trace inspection workflows
- [Export Data](https://docs.honeyhive.ai/v2/tracing/query-data.md) for querying trace data outside the UI
- [Custom Metrics](https://docs.honeyhive.ai/v2/tracing/client-side-evals.md) and [Online Evaluations](https://docs.honeyhive.ai/v2/monitoring/onlineevals.md) for understanding evaluator signals attached to traces
- [Get session tree by session ID](https://docs.honeyhive.ai/v2/api-reference-autogen/sessions/get-session-tree-by-session-id.md) and [Query events with filters and projections](https://docs.honeyhive.ai/v2/api-reference-autogen/events/query-events-with-filters-and-projections.md) for the v2 API shape behind session and event retrieval
- [HoneyHive CLI](https://docs.honeyhive.ai/v2/sdk-reference/cli.md) for terminal workflows
- the matching v2 integration guide under `https://docs.honeyhive.ai/v2/integrations/` for the user's framework when the failure is framework-specific

## Phase 0 - Ask Before Acting

Before changing code, prompts, dependencies, evaluators, datasets, experiment runs, or HoneyHive resources, understand the failure and get alignment.

If the host provides an ask-user-question or structured-question tool, use it for the few questions that determine the path. Prefer asking at most 2-4 targeted questions at once.

Clarify:

- **Failure target:** Does the user have a `session_id`, `event_id`, `run_id`, alert, evaluator failure, or only a vague complaint?
- **Mode:** Is this an offline improvement loop or a production or online issue?
- **Instrumentation state:** Is the app already instrumented in HoneyHive?
- **Edit tolerance:** Does the user want read-only RCA, a plan only, or approval for minimal code or resource changes after review?

If the failure target, repo subtree, or permission to mutate is unclear, stop and ask. Do not guess.

## Phase 1 - Read-Only Discovery

Run discovery before proposing changes.

1. **Find the exact workflow.** Identify the agent, service, route, job, notebook, script, or repo subtree involved. In a monorepo, scope all later work to the smallest relevant subtree.
2. **Detect HoneyHive versions and state.** Check manifests, lockfiles, and installed tooling for the HoneyHive SDK, CLI, tracer or instrumentor versions, plus any relevant framework version that could affect the failure mode. Also detect existing tracing setup, evaluators, prior experiment runs, datasets, and any alerting or regression workflow already in place.
3. **Check the CLI surface before relying on it.** Use `honeyhive --help` and namespace help before using commands. Prefer the CLI for HoneyHive resource operations whenever the needed command exists.
4. **Gather the smallest useful evidence set.** Start from one concrete failing example when possible: a failing session, event, run, evaluator result, user complaint tied to a time window, or one bad output from tests or logs.
5. **Keep discovery read-only.** Do not edit code. Do not create or modify datasets, datapoints, metrics/evaluators, runs, or alerts yet.

Discovery is read-only. Do not assume the app is already instrumented or that the user already has a fully built agent.

## Phase 2 - Choose the Path

Pick the smallest path that answers the user's immediate debugging question.

- **Instrumented + concrete failing resource:** If the user has a `session_id`, `event_id`, or `run_id`, inspect that exact failure first. Reconstruct the failure from HoneyHive data before proposing a fix.
- **Instrumented + vague complaint:** Narrow the complaint by time window, feature, evaluator signal, or complaint class. Turn the vague complaint into one concrete failing example before proposing changes.
- **Not instrumented yet:** Say clearly that trace-backed RCA is blocked. Offer the smallest next step:
  - use `honeyhive-instrument` first if the user wants trace visibility, or
  - run an offline improvement loop from tests, fixtures, logs, or user-provided examples if they want to improve behavior now.
- **Existing experiment runs:** Reuse them. Inspect the run, its metrics, and any baseline comparison before creating new evaluation resources.
- **No runs yet:** Keep the first pass focused on diagnosis and the smallest fix. Do not force a formal experiment setup just to debug one failure.
- **Python workflow:** Reuse an existing Python evaluation harness if one already exists. Do not assume the user wants to introduce one.
- **TypeScript or non-Python workflow:** Use HoneyHive CLI for HoneyHive resources and the repo's existing local harnesses, tests, or scripts for reproduction. Do not pretend Python-only helpers exist.
- **Offline issue:** Work from known failing examples, datapoints, runs, or tests.
- **Production or online issue:** Start read-only, use recent HoneyHive evidence, and keep the remediation path narrow before recommending broader changes.

## Phase 3 - Reconstruct the Failure

Use HoneyHive data first when it exists. Prefer the CLI when a command exists, then fall back to installed SDK or API usage only when needed.

Typical namespaces to inspect:

- `honeyhive events`
- `honeyhive experiments`
- `honeyhive metrics`
- `honeyhive datasets`
- `honeyhive datapoints`

Common read-only starting points:

- `honeyhive --help`
- `honeyhive events --help`
- `honeyhive experiments --help`
- `honeyhive metrics --help`

If the installed CLI exposes them, common read-only actions may include event search, run lookup, run listing, run comparison, and metric listing. Discover the exact subcommand names from the installed CLI help instead of assuming they exist from this skill text.

When reconstructing the failure:

1. Start from the exact failing resource if the user has one.
2. Review the full workflow when possible, not just the final output: user input, retrieved context, tool results, model steps, evaluator output, and final response.
3. Use session, event, and span metadata to identify the failing step when possible.
4. Find the first plausible failure point, not every downstream symptom.
5. Write observations before explanations. Prefer "tool call returned no documents before the bad answer" over "the model was confused."
6. Separate:
   - **symptom** - what the user noticed
   - **first plausible cause** - the earliest step that appears wrong
   - **owner** - prompt, retrieval, tool call, model call, parser, evaluator, or infrastructure boundary

Consult version-matched framework docs or changelogs only when the observed failure points there. Do not let broad framework research distract from trace-backed RCA.

If the user only has a vague complaint and there are many candidate traces, narrow to a small review set first.

## Phase 4 - Plan and Wait

Before mutating anything, present a concise plan and wait for user approval.

The plan should include:

- the failure target and the HoneyHive evidence reviewed
- the most likely root cause
- the repo subtree to inspect or edit
- whether any HoneyHive resource changes are proposed
- whether any local reproduction, experiment rerun, or comparison is proposed
- how validation will work

If the user asked for read-only RCA only, stop after presenting findings and next-step options. Do not proceed into edits or resource creation.

## Phase 5 - Apply the Minimal Fix

Only after approval, apply the smallest change that matches the evidence.

Good first-pass fixes:

- a prompt or instruction update
- a retrieval or query adjustment
- a tool invocation or argument fix
- a parser or schema guard
- an evaluator correction
- a small config or wiring change

Avoid:

- unrelated refactors
- framework upgrades by default
- broad rewrites
- hidden HoneyHive resource creation

Use the HoneyHive CLI for HoneyHive resource operations whenever the command exists. Use SDK or API calls only when the CLI does not expose the needed operation or when the change belongs inside the user's code path.

## Phase 6 - Validate and Stop

Validation should prove the failure no longer reproduces in the smallest reasonable loop.

Choose the lightest validation that fits the problem:

1. confirm the local behavior now matches the intended path
2. confirm the failing case no longer reproduces
3. confirm the bad pattern is no longer visible in HoneyHive, if new trace data is available
4. if the user wants regression tracking, hand off to `honeyhive-evaluate` to reuse or create the smallest useful experiment and compare against the failing baseline

After the minimal fix is validated, stop. Do not expand scope into broader instrumentation, evaluation, or refactors unless the user asks.

## Inline Investigation Summary

Use this output shape when it helps:

```text
Investigation Summary
- Failure target:
- Evidence reviewed:
- First plausible failure point:
- Owner:
- Recommended minimal fix:
- Validation plan:
- Open uncertainty:
```

## Gotchas

- **No trace-backed claims without traces.** If the app is not instrumented, say so and switch to an offline path or recommend `honeyhive-instrument`.
- **CLI-first for HoneyHive resources.** Use the CLI whenever it exposes the needed command. Do not hardcode undocumented commands from memory.
- **No hidden mutations.** Do not edit code or create or update datasets, datapoints, metrics/evaluators, runs, or alerts until the user approves the plan.
- **Do not chase every symptom.** Focus on the first plausible failure point.
- **Do not overfit to framework lore.** Consult version-matched framework docs or changelogs only when the observed failure points there.
- **Do not overbuild the fix.** Prefer one narrow improvement over a broad rewrite.
- **Do not force formal eval setup.** If no experiment workflow exists yet, offer `honeyhive-evaluate` as a follow-up instead of making it a prerequisite for every debug task.

## Doc Gap Protocol

If the CLI, installed HoneyHive version, framework integration, or trace-analysis path needed for the investigation is not covered well enough for a reliable next step, do not improvise a broad recipe. Tell the user what is missing, what you were able to verify, and suggest opening an issue at the public skills repo issue tracker (`metadata.feedback_url`) with the HoneyHive CLI or SDK version, framework, and scenario.
