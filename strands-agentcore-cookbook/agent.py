"""
Single-file Strands agent deployed via the AWS Bedrock AgentCore runtime.

This cookbook shows the smallest viable end-to-end shape:

    user request --> AgentCore runtime --> @app.entrypoint --> Strands Agent
                                                                    |
                                                                    +-- BedrockModel (Claude Sonnet 4.0)
                                                                    +-- @tool calculator
                                                                    +-- @tool current_time

HoneyHive is wired in at module load. Per the public docs, HoneyHive must be
initialized BEFORE importing strands so its auto-instrumentation hooks register
against Strands' OpenTelemetry tracer provider — the rc21+ SDK then maps
Strands' gen_ai.* spans into the agent / llm / tool typing HoneyHive renders.

Run locally:
    agentcore configure -e agent.py
    agentcore launch --local
    curl -X POST http://localhost:8080/invocations \\
        -H "Content-Type: application/json" \\
        -d '{"prompt": "What is 17 * 23?"}'

Deploy to AWS:
    agentcore launch
    agentcore invoke '{"prompt": "What time is it?"}'
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from bedrock_agentcore import BedrockAgentCoreApp
from dotenv import load_dotenv

# HoneyHive must be initialized before importing strands so the auto-instrumentation
# hooks register against Strands' OpenTelemetry tracer provider. See
# https://docs.honeyhive.ai/v2/integrations/strands.
from honeyhive import HoneyHiveTracer

load_dotenv(override=True)

tracer = HoneyHiveTracer.init(
    api_key=os.getenv("HH_API_KEY"),
    project=os.getenv("HH_PROJECT"),
    source="cookbook",
    session_name="strands-agentcore-demo",
)

# Imports below are intentionally delayed until after HoneyHiveTracer.init so
# Strands' OTEL tracer provider picks up the HoneyHive span processors.
from strands import Agent, tool  # noqa: E402
from strands.models import BedrockModel  # noqa: E402

# Default to Claude Sonnet 4.0 cross-region inference profile.
# Override via env var for a different region or to use an
# application-inference-profile ARN (e.g. for per-tenant cost tracking).
#
# Nationwide-style application inference profile:
# BEDROCK_MODEL_ID=arn:aws:bedrock:us-east-1:123456789012:application-inference-profile/abc123
#
# Strands' BedrockModel accepts either a model ID or an inference-profile ARN
# as `model_id` — no other code changes needed for the swap.
DEFAULT_MODEL_ID = "us.anthropic.claude-sonnet-4-20250514-v1:0"
MODEL_ID = os.getenv("BEDROCK_MODEL_ID", DEFAULT_MODEL_ID)
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")


@tool
def calculator(expression: str) -> str:
    """Evaluate a basic arithmetic expression like "2 + 2" or "(17 * 23) / 4".

    Only +, -, *, /, parentheses, and decimal numbers are accepted. The `**`
    exponentiation operator is rejected explicitly — `9**9**9` passes the
    charset filter but evaluates to a number with ~370M digits and would
    exhaust memory. Returns the numeric result as a string, or an error
    message if the expression is invalid.
    """
    allowed = set("0123456789.+-*/() ")
    if not expression or not set(expression) <= allowed:
        return f"error: expression contains unsupported characters: {expression!r}"
    if "**" in expression:
        return "error: exponentiation (**) is rejected to prevent DoS via large numbers"
    try:
        # Constrained to arithmetic-only chars above, so eval is safe here.
        result = eval(expression, {"__builtins__": {}}, {})  # noqa: S307
    except Exception as exc:  # pylint: disable=broad-except
        return f"error: {exc}"
    return str(result)


@tool
def current_time(timezone_name: str = "UTC") -> str:
    """Return the current time as an ISO-8601 string.

    Currently only "UTC" is supported. TODO: extend to accept IANA tz names
    like "America/New_York" using zoneinfo.ZoneInfo.
    """
    if timezone_name.upper() != "UTC":
        return f"error: only UTC is supported right now (got {timezone_name!r})"
    return datetime.now(timezone.utc).isoformat()


# TODO (Copilot demo): add a third tool here — e.g. a `lookup_customer(customer_id)`
# that returns a stub dict. Keep the @tool decorator and a clear docstring so
# the model knows when to call it; pass it into the Agent(tools=[...]) below.


SYSTEM_PROMPT = """You are a helpful assistant with access to tools.
- Use `calculator` for any arithmetic, even simple sums.
- Use `current_time` whenever the user asks about time or dates.
- If a tool errors, explain the error to the user instead of retrying blindly.
"""

agent = Agent(
    name="strands-agentcore-demo",
    model=BedrockModel(model_id=MODEL_ID, region_name=AWS_REGION),
    tools=[calculator, current_time],
    system_prompt=SYSTEM_PROMPT,
)

app = BedrockAgentCoreApp()


@app.entrypoint
def invoke(payload: dict[str, Any]) -> dict[str, Any]:
    """AgentCore entrypoint. Receives the JSON body of POST /invocations."""
    prompt = payload.get("prompt", "")
    if not prompt:
        return {"result": "error: payload missing required `prompt` field"}

    # TODO (Copilot demo): enrich the HoneyHive session with payload metadata
    # — e.g. tracer.enrich_session(metadata={"prompt_length": len(prompt)}) —
    # so the trace in HoneyHive carries request context.

    result = agent(prompt)
    return {"result": str(result.message)}


if __name__ == "__main__":
    # Serves at http://localhost:8080/invocations for local dev.
    app.run()
