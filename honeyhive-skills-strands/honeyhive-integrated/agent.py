"""
Strands + OpenAI agent with HoneyHive tracing.

Run:
    uv run python agent.py "What is 17 * 23?"
"""

from __future__ import annotations

import os
import re
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv(override=True)

# HoneyHive must be initialized before importing strands so auto-instrumentation
# hooks register against Strands' OpenTelemetry tracer provider.
from honeyhive import HoneyHiveTracer  # noqa: E402

tracer = HoneyHiveTracer.init(
    api_key=os.getenv("HH_API_KEY"),
    project=os.getenv("HH_PROJECT"),
    source=os.getenv("HH_SOURCE", "cookbook"),
)

from strands import Agent, tool  # noqa: E402
from strands.models.openai import OpenAIModel  # noqa: E402

DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")


def _parse_numeric_literals(expression: str) -> list[float]:
    literals: list[float] = []
    for match in re.finditer(r"\d+(?:\.\d+)?", expression):
        literals.append(float(match.group(0)))
    return literals


def _is_power_of_two(value: float) -> bool:
    if value <= 0 or not value.is_integer():
        return False
    as_int = int(value)
    return (as_int & (as_int - 1)) == 0


def _is_exponentiation_workaround(expression: str) -> bool:
    """Reject common ways to compute powers after ** is blocked."""
    if "*" not in expression:
        return False

    factors = [part.strip() for part in expression.split("*")]
    numeric_factors = []
    for factor in factors:
        stripped = factor.strip("() ")
        if stripped.replace(".", "", 1).isdigit():
            numeric_factors.append(stripped)
    if len(numeric_factors) >= 3 and len(set(numeric_factors)) == 1:
        return True

    if expression.count("*") >= 1:
        numbers = _parse_numeric_literals(expression)
        if len(numbers) >= 2 and all(_is_power_of_two(number) for number in numbers):
            product = 1
            for number in numbers:
                product *= int(number)
            if product >= 2**30:
                return True

    return False


@tool
def calculator(expression: str) -> str:
    """Evaluate a basic arithmetic expression like "2 + 2" or "(17 * 23) / 4".

    Only +, -, *, /, parentheses, and decimal numbers are accepted.
    Returns the numeric result as a string, or an error message if invalid.
    """
    allowed = set("0123456789.+-*/() ")
    if not expression or not set(expression) <= allowed:
        return f"error: expression contains unsupported characters: {expression!r}"
    if "**" in expression:
        return "error: exponentiation (**) is rejected to prevent DoS via large numbers"
    if _is_exponentiation_workaround(expression):
        return (
            "error: repeated multiplication of the same factor is rejected "
            "(possible exponentiation workaround)"
        )
    try:
        result = eval(expression, {"__builtins__": {}}, {})  # noqa: S307
    except Exception as exc:  # pylint: disable=broad-except
        return f"error: {exc}"
    return str(result)


@tool
def current_time(timezone_name: str = "UTC") -> str:
    """Return the current time as an ISO-8601 string. Only UTC is supported."""
    if timezone_name.upper() != "UTC":
        return f"error: only UTC is supported right now (got {timezone_name!r})"
    return datetime.now(timezone.utc).isoformat()


SYSTEM_PROMPT = """You are a helpful assistant with access to tools.
- Use `calculator` for any arithmetic, even simple sums.
- Use `current_time` whenever the user asks about time or dates.
- If a tool errors on exponentiation (**), explain that exponentiation is not
  supported and stop. Do not compute the value another way and do not state the
  numeric answer from memory.
- When `current_time` returns an ISO-8601 timestamp, include that exact value
  in your answer (do not rewrite it as a casual date/time phrase).
- When the user asks for an exact decimal, give the full calculator result
  without rounding or words like "approximately".
- Reply with plain numbers and text, not LaTeX math notation.
"""

model = OpenAIModel(
    client_args={"api_key": os.getenv("OPENAI_API_KEY")},
    model_id=DEFAULT_MODEL,
)

agent = Agent(
    name="honeyhive-skills-strands-integrated",
    model=model,
    tools=[calculator, current_time],
    system_prompt=SYSTEM_PROMPT,
    callback_handler=None,
)


def message_to_text(message: object) -> str:
    if isinstance(message, dict):
        parts = message.get("content", [])
        text = " ".join(p.get("text", "") for p in parts if isinstance(p, dict))
        return text or str(message)
    return str(message)


def run_agent(prompt: str) -> str:
    """Run the Strands agent on a single prompt and return the text response."""
    result = agent(prompt)
    return message_to_text(result.message)


def main() -> None:
    prompt = " ".join(sys.argv[1:]).strip() or "What is 17 * 23?"
    tracer.create_session(
        session_name="honeyhive-skills-strands-integrated",
        inputs={"prompt": prompt},
    )
    print(run_agent(prompt))


if __name__ == "__main__":
    main()
