"""Score HoneyHive sessions with Strands Evals evaluators and write the scores back to HoneyHive.

Usage:
    python example.py <session_id> [<session_id> ...]

The sessions can come from any Strands agent that sends traces to HoneyHive, in Python or TypeScript.
"""

from __future__ import annotations

import os
import sys

import httpx
from dotenv import load_dotenv
from strands.models.openai import OpenAIModel
from strands_evals import Case, Experiment
from strands_evals.evaluators import HelpfulnessEvaluator, ToolSelectionAccuracyEvaluator

from honeyhive_provider import HoneyHiveProvider


def main(session_ids: list[str]) -> None:
    load_dotenv()
    provider = HoneyHiveProvider()  # Reads HH_API_KEY and HH_API_URL

    # Strands Evals judges use Amazon Bedrock by default. This example uses OpenAI instead.
    judge = OpenAIModel(model_id="gpt-4.1-mini")
    evaluators = [HelpfulnessEvaluator(model=judge), ToolSelectionAccuracyEvaluator(model=judge)]

    # The provider fetches each session by its ID, so the case input is only a label.
    # Case names must be unique, and the report identifies rows by case name.
    cases = [Case(name=sid, session_id=sid, input=sid) for sid in session_ids]
    report = Experiment(cases=cases, evaluators=evaluators).run_evaluations(provider.as_task())

    # Each report row is one (case, evaluator) pair. Collect the scores per session.
    scores: dict[str, dict[str, float | str]] = {sid: {} for sid in session_ids}
    rows = zip(report.cases, report.scores, report.reasons, report.detailed_results, strict=True)
    for row, score, reason, detail in rows:
        if not detail:
            # Strands Evals reports a failed fetch as a score of 0 with no detailed results.
            # Writing that 0 back would record a verdict that no judge made.
            print(f"{row['name']}: skipped {row['evaluator']} ({reason})", file=sys.stderr)
            continue
        metric = f"strands.{row['evaluator']}"
        scores[row["name"]][metric] = score
        scores[row["name"]][f"{metric}_explanation"] = reason

    api_url = os.environ.get("HH_API_URL", "https://api.dp1.us.honeyhive.ai").rstrip("/")
    headers = {"Authorization": f"Bearer {os.environ['HH_API_KEY']}"}
    with httpx.Client(base_url=api_url, headers=headers, timeout=30) as client:
        for session_id, metrics in scores.items():
            if not metrics:
                continue
            # The session event ID is the session ID. HoneyHive merges these keys into existing metrics.
            try:
                client.put(f"/v1/events/{session_id}", json={"metrics": metrics}).raise_for_status()
            except httpx.HTTPError as e:
                print(f"{session_id}: could not write scores ({e})", file=sys.stderr)
                continue
            print(session_id, {k: v for k, v in metrics.items() if not k.endswith("_explanation")})


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("Usage: python example.py <session_id> [<session_id> ...]")
    main(sys.argv[1:])
