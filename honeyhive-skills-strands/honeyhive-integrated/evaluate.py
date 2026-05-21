"""
Evaluate the Strands agent with HoneyHive experiments.

Run:
    uv run python evaluate.py
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv(override=True)

from honeyhive import evaluate  # noqa: E402

from agent import DEFAULT_MODEL, run_agent_for_eval  # noqa: E402
from eval_harness import (  # noqa: E402
    DATASET,
    JUDGE_MODEL,
    MAX_WORKERS,
    answer_correct,
    make_run_datapoint,
    print_evaluator_comparison,
    task_quality,
)

EXPERIMENT_NAME = "honeyhive-skills-strands-integrated-eval"


if __name__ == "__main__":
    print(f"Project: {os.getenv('HH_PROJECT', 'Strands')}")
    print(f"Agent model: {os.getenv('OPENAI_MODEL', DEFAULT_MODEL)}")
    print(f"Judge model: {JUDGE_MODEL}")
    print(f"Max workers: {MAX_WORKERS}")

    result = evaluate(
        function=make_run_datapoint(run_agent_for_eval),
        dataset=DATASET,
        evaluators=[answer_correct, task_quality],
        name=EXPERIMENT_NAME,
        max_workers=MAX_WORKERS,
        verbose=False,
    )

    print(f"Run ID: {result.run_id}")
    print(f"Success: {result.success}")
    if result.metrics:
        print(f"Metrics: {result.metrics.list_metrics()}")

    print_evaluator_comparison(result, DATASET)
