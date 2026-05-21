"""
Evaluate the Strands agent with HoneyHive experiments.

Run:
    uv run python evaluate.py
"""

from __future__ import annotations

import json
import math
import os
import re

from dotenv import load_dotenv
from openai import OpenAI

# Load local .env before other imports so HH_PROJECT wins over workspace direnv.
load_dotenv(override=True)

from honeyhive import evaluate  # noqa: E402

from agent import run_agent  # noqa: E402

JUDGE_MODEL = os.getenv("OPENAI_JUDGE_MODEL", os.getenv("OPENAI_MODEL", "gpt-5-mini"))
judge_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

JUDGE_SYSTEM = """You are a QA judge for a Strands assistant with two tools:
- calculator: basic +, -, *, /, parentheses, decimals. Rejects ** exponentiation.
- current_time: UTC only.

Score pass/fail as binary:
  1 - Response satisfies the success criteria on substance.
  0 - Wrong numeric result, hallucinated answer, ignored a tool error, used the
      wrong tool, skipped a required part of a multi-part request, or failed to
      explain a tool limitation when asked about unsupported operations/timezones.

Formatting leniency (still pass):
- Equivalent numbers count as correct (7 vs 7.0, 998001 vs 998,001).
- Minor decimal truncation is fine if clearly the same value.
- Prose around a correct answer is fine; the user did not have to reply with a bare number.
- A valid ISO-8601 UTC timestamp satisfies time requests even with extra words.

Still fail:
- Inventing a numeric answer for unsupported ** exponentiation.
- Fabricating non-UTC local times.
- Missing a required second result in multi-part prompts.
- Returning a made-up value for division by zero.

Return strictly JSON: {"score": 0 | 1}."""

DATASET = [
    # --- baseline ---
    {
        "inputs": {"prompt": "What is 17 * 23?"},
        "ground_truth": {
            "answer": "391",
            "criteria": "Correctly states that 17 * 23 equals 391.",
        },
    },
    {
        "inputs": {"prompt": "What is 15 + 27?"},
        "ground_truth": {
            "answer": "42",
            "criteria": "Correctly states that 15 + 27 equals 42.",
        },
    },
    {
        "inputs": {"prompt": "Compute (100 - 37) / 9. Reply with just the number."},
        "ground_truth": {
            "answer": "7",
            "criteria": "Gives 7 as the result of (100 - 37) / 9.",
        },
    },
    {
        "inputs": {"prompt": "What is the current time in UTC?"},
        "ground_truth": {
            "pattern": r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}",
            "criteria": "Returns a plausible current UTC timestamp in ISO-8601 form.",
        },
    },
    {
        "inputs": {"prompt": "What is 2 ** 50?"},
        "ground_truth": {
            "require_tool_limitation": True,
            "criteria": (
                "Explains that exponentiation is not supported by the calculator "
                "(or that ** is rejected) and does not invent a numeric answer "
                "for 2**50."
            ),
        },
    },
    # --- hard ---
    {
        "inputs": {
            "prompt": (
                "I have 847 apples, give away 129, and split the rest equally among "
                "7 friends. How many apples does each friend get? Give the exact decimal."
            ),
        },
        "ground_truth": {
            "answer": "102.57142857142858",
            "criteria": (
                "Correctly computes (847 - 129) / 7 and gives the exact decimal "
                "102.57142857142858 (or an equivalent precise decimal)."
            ),
        },
    },
    {
        "inputs": {
            "prompt": "What is ((19 + 31) * 4 - 15) / 13? Reply with the full decimal result.",
        },
        "ground_truth": {
            "answer": "14.230769230769231",
            "criteria": (
                "Correctly evaluates ((19 + 31) * 4 - 15) / 13 as "
                "14.230769230769231 (or an equivalent precise decimal)."
            ),
        },
    },
    {
        "inputs": {"prompt": "What is 999 * 999?"},
        "ground_truth": {
            "answer": "998001",
            "criteria": "Correctly states that 999 * 999 equals 998001.",
        },
    },
    {
        "inputs": {"prompt": "What is 123456789 * 987654321?"},
        "ground_truth": {
            "answer": "121932631112635269",
            "criteria": (
                "Correctly states that 123456789 * 987654321 equals "
                "121932631112635269."
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
            "criteria": (
                "Includes a plausible current UTC timestamp and states that "
                "17 + 23 equals 40."
            ),
        },
    },
    {
        "inputs": {
            "prompt": (
                "What is 6 / 2 * 3? Use the calculator and reply with just the number."
            ),
        },
        "ground_truth": {
            "answer": "9",
            "criteria": (
                "Uses the calculator and gives 9 as the result of 6 / 2 * 3 "
                "(left-to-right as Python evaluates it)."
            ),
        },
    },
]


def run_strands_datapoint(datapoint: dict) -> dict:
    prompt = datapoint["inputs"]["prompt"]
    return {"prompt": prompt, "response": run_agent(prompt)}


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

        # Accept minor float formatting differences and short truncation tails.
        expected_text = f"{expected_value:.15f}".rstrip("0").rstrip(".")
        candidate_text = f"{candidate:.15f}".rstrip("0").rstrip(".")
        if expected_text == candidate_text:
            return True
        if expected_text.startswith(candidate_text) or candidate_text.startswith(expected_text):
            shared = min(len(expected_text), len(candidate_text))
            if shared >= max(len(expected_text) - 2, 1):
                return True

    return False


def _mentions_tool_limitation(text: str) -> bool:
    lowered = text.lower()
    keywords = (
        "not supported",
        "unsupported",
        "rejected",
        "cannot",
        "can't",
        "error",
        "exponent",
        "**",
    )
    return any(keyword in lowered for keyword in keywords)


def _claims_large_numeric_answer(response: str) -> bool:
    for value in _extract_numbers(response):
        if abs(value) >= 1_000_000:
            return True
    return False


def answer_correct(outputs: dict, inputs: dict, ground_truth: dict | None) -> float:
    """Fast deterministic checks for exact answers and simple patterns."""
    if not ground_truth:
        return 1.0

    response = str(outputs.get("response", ""))
    lowered = response.lower()

    if ground_truth.get("require_tool_limitation"):
        if not _mentions_tool_limitation(response):
            return 0.0
        if _claims_large_numeric_answer(response):
            return 0.0

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
    """LLM judge for rubric-based pass/fail on nuanced tool-use cases."""
    if not ground_truth or not ground_truth.get("criteria"):
        return 1.0

    prompt = inputs["prompt"]
    response = str(outputs.get("response", ""))
    criteria = ground_truth["criteria"]
    reference = ground_truth.get("answer")

    user_content = (
        f"User prompt: {prompt}\n"
        f"Agent response: {response}\n"
        f"Success criteria: {criteria}\n"
        "Scoring reminder: accept equivalent numeric formatting, comma separators, "
        "7 vs 7.0 vs 9 vs 9.0, and prose around correct answers. "
        "Only fail clear substantive mistakes.\n"
        "Respond in JSON only.\n"
    )
    if reference:
        user_content += f"Reference answer (if applicable): {reference}\n"

    # gpt-5-* models only support the default temperature; omit the parameter.
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
    prompt_by_id = {}
    for idx, item in enumerate(dataset):
        prompt_by_id[f"idx-{idx}"] = item["inputs"]["prompt"]

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


if __name__ == "__main__":
    project = os.getenv("HH_PROJECT", "default")
    agent_model = os.getenv("OPENAI_MODEL", "gpt-5-mini")
    print(f"Project: {project}")
    print(f"Agent model: {agent_model}")
    print(f"Judge model: {JUDGE_MODEL}")

    result = evaluate(
        function=run_strands_datapoint,
        dataset=DATASET,
        evaluators=[answer_correct, task_quality],
        project=project,
        name="honeyhive-skills-strands-no-honeyhive-eval",
        max_workers=1,
        verbose=False,
    )

    print(f"Run ID: {result.run_id}")
    print(f"Success: {result.success}")
    if result.metrics:
        print(f"Metrics: {result.metrics.list_metrics()}")

    print_evaluator_comparison(result, DATASET)
