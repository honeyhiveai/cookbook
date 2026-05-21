"""
Minimal Strands + OpenAI agent (baseline, no HoneyHive).

Run:
    uv run python agent.py "What is 17 * 23?"
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv
from strands import Agent, tool
from strands.models.openai import OpenAIModel

load_dotenv(override=True)

DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")
ALLOWED_CALC_CHARS = set("0123456789.+-*/() ")

SYSTEM_PROMPT = """You are a helpful assistant with access to tools.
- Use `calculator` for any arithmetic, even simple sums.
- Use `current_time` whenever the user asks about time or dates.
- If a tool errors, try another valid approach when you can (e.g. rewrite the
  expression with supported operators).
- When `current_time` returns an ISO-8601 timestamp, include that exact value
  in your answer (do not rewrite it as a casual date/time phrase).
- When the user asks for an exact decimal, give the full calculator result
  without rounding or words like "approximately".
- Reply with plain numbers and text, not LaTeX math notation.
"""


@tool
def calculator(expression: str) -> str:
    """Evaluate a basic arithmetic expression like "2 + 2" or "(17 * 23) / 4".

    Only +, -, *, /, parentheses, and decimal numbers are accepted.
    Returns the numeric result as a string, or an error message if invalid.
    """
    if not expression or not set(expression) <= ALLOWED_CALC_CHARS:
        return f"error: expression contains unsupported characters: {expression!r}"
    if "**" in expression:
        return "error: exponentiation (**) is rejected — use * or break the problem into steps"
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


def message_to_text(message: object) -> str:
    if not isinstance(message, dict):
        return str(message)
    parts = message.get("content", [])
    text = " ".join(p.get("text", "") for p in parts if isinstance(p, dict))
    return text or str(message)


agent = Agent(
    name="honeyhive-skills-strands-no-honeyhive",
    model=OpenAIModel(
        client_args={"api_key": os.getenv("OPENAI_API_KEY")},
        model_id=DEFAULT_MODEL,
    ),
    tools=[calculator, current_time],
    system_prompt=SYSTEM_PROMPT,
    callback_handler=None,
)


def run_agent(prompt: str) -> str:
    return message_to_text(agent(prompt).message)


def main() -> None:
    prompt = " ".join(sys.argv[1:]).strip() or "What is 17 * 23?"
    print(run_agent(prompt))


if __name__ == "__main__":
    main()
