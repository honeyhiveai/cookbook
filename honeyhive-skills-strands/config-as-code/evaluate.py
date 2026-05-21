"""
Evaluate the Strands agent with HoneyHive experiments.

Run:
    uv run python evaluate.py

Datapoints load from `.honeyhive/datapoints/` (config as code). HoneyHive evaluate()
runs the agent over the dataset and scores each datapoint with:
  - answer_correct  — code check (numeric answer, patterns, required values)
  - task_quality    — LLM judge (tool use vs guessing; skips re-checking numbers)
"""

from __future__ import annotations

import json
import math
import os
import re
from pathlib import Path

import yaml
from dotenv import load_dotenv
from honeyhive import evaluate
from openai import OpenAI

load_dotenv(override=True)

from agent import DEFAULT_MODEL, run_agent_for_eval  # noqa: E402

HONEYHIVE_DIR = Path(__file__).resolve().parent / ".honeyhive"
JUDGE_MODEL = os.getenv("OPENAI_JUDGE_MODEL", os.getenv("OPENAI_MODEL", "gpt-5-mini"))
MAX_WORKERS = int(os.getenv("EVAL_MAX_WORKERS", "4"))
EXPERIMENT_NAME = "honeyhive-skills-strands-config-as-code-eval"

judge_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

JUDGE_SYSTEM = """You are a QA judge for a Strands assistant with two tools:
- calculator: basic +, -, *, /, parentheses, decimals. Rejects ** in expressions.
- current_time: UTC only.

You work alongside a separate code evaluator (`answer_correct`) that checks numeric
answers, regex patterns, and required substrings. Do NOT re-grade whether the final
number or timestamp string is correct when the rubric says the code check handles it.

Your primary job on arithmetic prompts: detect **guessing** — stating a correct-looking
result with no evidence the agent used the calculator or an equivalent step-by-step
computation.

Score pass/fail as binary:
  1 - Meets the success criteria; for math, shows evidence of calculation/tool use.
  0 - Guessed without calculating when required; ignored a tool error; skipped a part;
      fabricated unsupported data.

Still fail:
- Correct numeric answer but clearly guessed without tool use when calculation was required.
- Fabricating non-UTC local times when only UTC is supported.
- Missing a required second result in multi-part prompts.
- Returning a made-up value for division by zero instead of reporting the tool error.

Return strictly JSON: {"score": 0 | 1}."""


def load_dataset() -> list[dict]:
    """Load datapoints from .honeyhive/datapoints/*.yaml (config as code)."""
    datapoints_dir = HONEYHIVE_DIR / "datapoints"
    if not datapoints_dir.is_dir():
        raise FileNotFoundError(f"Missing datapoints directory: {datapoints_dir}")

    dataset: list[dict] = []
    for path in sorted(datapoints_dir.glob("*.yaml")):
        raw = yaml.safe_load(path.read_text())
        entry: dict = {"inputs": raw["inputs"]}
        if raw.get("ground_truth") is not None:
            entry["ground_truth"] = raw["ground_truth"]
        dataset.append(entry)
    return dataset


DATASET = load_dataset()

_NUMBER_PATTERN = re.compile(
    r"[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?|\.\d+"
)


def _parse_number(raw: str) -> float | None:
    cleaned = raw.replace(",", "").strip()
    if not cleaned or cleaned in {".", "-", "+", "-.", "+."}:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _extract_numbers(text: str) -> list[float]:
    return [
        parsed
        for match in _NUMBER_PATTERN.finditer(text)
        if (parsed := _parse_number(match.group(0))) is not None
    ]


def _numbers_equivalent(expected: str, response: str) -> bool:
    expected_value = _parse_number(expected)
    if expected_value is None:
        return expected in response

    for candidate in _extract_numbers(response):
        if math.isclose(expected_value, candidate, rel_tol=0, abs_tol=1e-9):
            return True

        expected_text = f"{expected_value:.15f}".rstrip("0").rstrip(".")
        candidate_text = f"{candidate:.15f}".rstrip("0").rstrip(".")
        if expected_text == candidate_text:
            return True
        if expected_text.startswith(candidate_text) or candidate_text.startswith(expected_text):
            shared = min(len(expected_text), len(candidate_text))
            if shared >= max(len(expected_text) - 2, 1):
                return True

    return False


def answer_correct(outputs: dict, inputs: dict, ground_truth: dict | None) -> float:
    """Code evaluator: correct numeric answer, patterns, and required values."""
    if not ground_truth:
        return 1.0

    response = str(outputs.get("response", ""))
    lowered = response.lower()

    if "answer" in ground_truth and not _numbers_equivalent(
        str(ground_truth["answer"]), response
    ):
        return 0.0

    if "pattern" in ground_truth and not re.search(ground_truth["pattern"], response):
        return 0.0

    if "must_mention_all" in ground_truth:
        for needle in ground_truth["must_mention_all"]:
            if _parse_number(str(needle)) is not None:
                if not _numbers_equivalent(str(needle), response):
                    return 0.0
            elif str(needle).lower() not in lowered:
                return 0.0

    return 1.0


def task_quality(outputs: dict, inputs: dict, ground_truth: dict | None) -> float:
    """LLM evaluator: tool use and anti-guessing (answer_correct handles numbers)."""
    if not ground_truth or not ground_truth.get("criteria"):
        return 1.0

    if ground_truth.get("requires_calculation") and answer_correct(outputs, inputs, ground_truth) == 0.0:
        return 0.0

    prompt = inputs["prompt"]
    response = str(outputs.get("response", ""))
    criteria = ground_truth["criteria"]
    reference = ground_truth.get("answer")

    user_content = (
        f"User prompt: {prompt}\n"
        f"Agent response: {response}\n"
        f"Success criteria: {criteria}\n"
    )
    if ground_truth.get("requires_calculation"):
        user_content += (
            "Note: answer_correct already verified the numeric result matches the "
            f"reference ({reference}). Judge ONLY whether the agent calculated via "
            "tools/steps vs guessed. Fail a correct number with no evidence of "
            "computation.\n"
        )
    user_content += "Respond in JSON only.\n"
    if reference and not ground_truth.get("requires_calculation"):
        user_content += f"Reference answer (if applicable): {reference}\n"

    completion = judge_client.chat.completions.create(
        model=JUDGE_MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": JUDGE_SYSTEM},
            {"role": "user", "content": user_content},
        ],
    )

    raw = completion.choices[0].message.content
    if not raw:
        raise ValueError("Judge returned an empty response.")

    score = float(json.loads(raw)["score"])
    if score not in {0.0, 1.0}:
        raise ValueError(f"Judge score must be 0 or 1, got {score}.")
    return score


def _print_evaluator_comparison(result, dataset: list[dict]) -> None:
    if not result.datapoints:
        print("\nNo per-datapoint metrics returned from backend.")
        return

    print("\nCode check vs LLM judge")
    print("-" * 72)
    agree = 0
    for idx, dp in enumerate(result.datapoints):
        prompt = dataset[idx]["inputs"]["prompt"] if idx < len(dataset) else dp.datapoint_id
        short = prompt if len(prompt) <= 56 else prompt[:53] + "..."
        scores = {m.name: m.value for m in dp.metrics}
        code = scores.get("answer_correct")
        judge = scores.get("task_quality")
        agree += code == judge
        flag = "agree" if code == judge else "DIFF"
        print(f"{idx + 1:2}. [{flag:5}] code={code} judge={judge} | {short}")

    print("-" * 72)
    print(f"Agreement: {agree}/{len(result.datapoints)}")


def _run_datapoint(datapoint: dict) -> dict:
    prompt = datapoint["inputs"]["prompt"]
    return {"prompt": prompt, "response": run_agent_for_eval(prompt)}


if __name__ == "__main__":
    print(f"Project: {os.getenv('HH_PROJECT', 'Strands')}")
    print(f"Agent model: {os.getenv('OPENAI_MODEL', DEFAULT_MODEL)}")
    print(f"Judge model: {JUDGE_MODEL}")
    print(f"Max workers: {MAX_WORKERS}")

    result = evaluate(
        function=_run_datapoint,
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

    _print_evaluator_comparison(result, DATASET)
