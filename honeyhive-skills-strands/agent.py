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

DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


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
- If a tool errors, explain the error to the user instead of retrying blindly.
"""

model = OpenAIModel(
    client_args={"api_key": os.getenv("OPENAI_API_KEY")},
    model_id=DEFAULT_MODEL,
)

agent = Agent(
    name="honeyhive-skills-strands",
    model=model,
    tools=[calculator, current_time],
    system_prompt=SYSTEM_PROMPT,
    callback_handler=None,
)


def main() -> None:
    prompt = " ".join(sys.argv[1:]).strip() or "What is 17 * 23?"
    result = agent(prompt)
    msg = result.message
    if isinstance(msg, dict):
        parts = msg.get("content", [])
        text = " ".join(p.get("text", "") for p in parts if isinstance(p, dict))
        print(text or msg)
    else:
        print(msg)


if __name__ == "__main__":
    main()
