"""Shared HoneyHive experiment dataset and evaluators for the Strands agent."""

from __future__ import annotations

import json
import math
import os
import re
from collections.abc import Callable

from openai import OpenAI

JUDGE_MODEL = os.getenv("OPENAI_JUDGE_MODEL", os.getenv("OPENAI_MODEL", "gpt-5-mini"))
MAX_WORKERS = int(os.getenv("EVAL_MAX_WORKERS", "4"))
# Strands: one in-flight invocation per Agent instance; evaluate() uses a fresh
# Agent per datapoint via make_eval_runner() so workers can run in parallel.
judge_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

JUDGE_SYSTEM = """You are a QA judge for a Strands assistant with two tools:
- calculator: basic +, -, *, /, parentheses, decimals. Rejects ** in expressions.
- current_time: UTC only.

You work alongside a separate code evaluator (`answer_correct`) that checks numeric
answers, regex patterns, and required substrings. Do NOT re-grade whether the final
number or timestamp string is correct when the rubric says the code check handles it.

Your primary job on arithmetic prompts: detect **guessing** — stating a correct-looking
result with no evidence the agent used the calculator or an equivalent step-by-step
computation. Fail when the response looks like memorization or hallucination rather
than tool-backed work (e.g. bare "391" with no tool context for 17*23; a huge integer
for 2**50 with no sign of calculator use after ** was rejected).

Score pass/fail as binary:
  1 - Meets the success criteria; for math, shows evidence of calculation/tool use.
  0 - Guessed without calculating when calculation was required; ignored a tool error;
      used the wrong tool; skipped a required part; fabricated unsupported data.

Formatting leniency (still pass):
- Prose around a correct answer is fine.
- Equivalent numeric formatting is fine (handled by code check when applicable).

Still fail:
- Correct numeric answer but clearly guessed without tool use when calculation was required.
- Fabricating non-UTC local times when only UTC is supported.
- Missing a required second result in multi-part prompts.
- Returning a made-up value for division by zero instead of reporting the tool error.

Return strictly JSON: {"score": 0 | 1}."""

DATASET = [
    {
        "inputs": {"prompt": "What is 17 * 23?"},
        "ground_truth": {
            "answer": "391",
            "requires_calculation": True,
            "criteria": (
                "Used the calculator (or showed equivalent tool-backed steps); did not "
                "only guess 391 from memory with no sign of computation."
            ),
        },
    },
    {
        "inputs": {"prompt": "What is the current time in UTC?"},
        "ground_truth": {
            "pattern": r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}",
            "criteria": (
                "Used current_time (or clearly relied on its output); did not invent "
                "a plausible-looking timestamp from memory alone."
            ),
        },
    },
    {
        "inputs": {"prompt": "What is 2 ** 50?"},
        "ground_truth": {
            "answer": "1125899906842624",
            "requires_calculation": True,
            "criteria": (
                "After ** was rejected, computed the result via calculator-friendly "
                "steps (e.g. repeated multiplication); did not guess the huge "
                "integer from memory alone."
            ),
        },
    },
    {
        "inputs": {"prompt": "What is the current time in Tokyo?"},
        "ground_truth": {
            "criteria": (
                "Explains that only UTC is supported by current_time and does not "
                "fabricate a Tokyo local time."
            ),
        },
    },
    {
        "inputs": {
            "prompt": (
                "First get the current UTC time, then use the calculator to add "
                "17 and 23. Reply with both results."
            ),
        },
        "ground_truth": {
            "must_mention_all": ["40"],
            "pattern": r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}",
            "requires_calculation": True,
            "criteria": (
                "Used current_time for UTC and calculator for 17+23; did not guess "
                "either result without tool-backed evidence."
            ),
        },
    },
    {
        "inputs": {
            "prompt": "Use the calculator on 10 / 0 and tell me exactly what happens.",
        },
        "ground_truth": {
            "criteria": (
                "Reports the calculator/tool error for division by zero instead of "
                "returning a made-up numeric result."
            ),
        },
    },
]

_NUMBER_PATTERN = re.compile(
    r"[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?|\.\d+"
)


def make_run_datapoint(run_agent: Callable[[str], str]) -> Callable[[dict], dict]:
    def run_strands_datapoint(datapoint: dict) -> dict:
        prompt = datapoint["inputs"]["prompt"]
        return {"prompt": prompt, "response": run_agent(prompt)}

    return run_strands_datapoint


def _parse_number(raw: str) -> float | None:
    cleaned = raw.replace(",", "").strip()
    if not cleaned or cleaned in {".", "-", "+", "-.", "+."}:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _extract_numbers(text: str) -> list[float]:
    numbers: list[float] = []
    for match in _NUMBER_PATTERN.finditer(text):
        parsed = _parse_number(match.group(0))
        if parsed is not None:
            numbers.append(parsed)
    return numbers


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
    """Deterministic check: correct numeric answer, patterns, and required values."""
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
    """LLM judge: tool use and anti-guessing; numeric correctness is answer_correct."""
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


def print_evaluator_comparison(result, dataset: list[dict]) -> None:
    """Print side-by-side code vs LLM judge scores per datapoint."""
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
        if code == judge:
            agree += 1
            flag = "agree"
        else:
            flag = "DIFF"
        print(f"{idx + 1:2}. [{flag:5}] code={code} judge={judge} | {short}")

    total = len(result.datapoints)
    print("-" * 72)
    print(f"Agreement: {agree}/{total}")
