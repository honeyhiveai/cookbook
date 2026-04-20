"""
Evaluate the customer support agent using HoneyHive experiments.

Run either version and compare `response_quality` scores in HoneyHive:
    uv run python evaluate.py --version v1
    uv run python evaluate.py --version v2
"""

import argparse
import json
import uuid

from dotenv import load_dotenv
from google import genai
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import GenerateContentConfig
from openinference.instrumentation.google_adk import GoogleADKInstrumentor

from honeyhive import evaluate

from main import APP_NAME, USER_ID, handle_customer_query, load_agent_module

load_dotenv(override=True)

JUDGE_MODEL = "gemini-flash-latest"
genai_client = genai.Client()


def make_run_support_agent(build_agents):
    """Build a run_support_agent task bound to a specific agent version."""

    async def run_support_agent(datapoint: dict) -> dict:
        """Run the support agent on a single datapoint."""
        session_service = InMemorySessionService()
        session_id = str(uuid.uuid4())
        await session_service.create_session(
            app_name=APP_NAME, user_id=USER_ID, session_id=session_id
        )
        runner = Runner(
            agent=build_agents(),
            app_name=APP_NAME,
            session_service=session_service,
        )

        response = await handle_customer_query(
            runner, session_id, datapoint["inputs"]["query"]
        )
        return {"response": response}

    return run_support_agent


JUDGE_SYSTEM = (
    "You are a strict customer-support QA reviewer. Score the agent's response "
    "on a 3-point scale:\n"
    "  1   - Fully helpful. Directly answers the question with concrete specifics "
    "(amounts, dates, article IDs, troubleshooting steps).\n"
    "  0.5 - Partially helpful. Addresses the question but is vague, incomplete, "
    "or missing key specifics.\n"
    "  0   - Unhelpful. Apologizes, admits a tool error, dodges the question, or "
    "returns no actionable information.\n"
    'Return strictly {"score": 0 | 0.5 | 1}.'
)


def response_quality(outputs: dict, inputs: dict) -> float:
    """Judge whether the response is fully / partially / not helpful."""
    result = genai_client.models.generate_content(
        model=JUDGE_MODEL,
        contents=(
            f"Customer query: {inputs['query']}\n"
            f"Agent response: {outputs.get('response', '')}"
        ),
        config=GenerateContentConfig(
            system_instruction=JUDGE_SYSTEM,
            temperature=0,
            response_mime_type="application/json",
        ),
    )
    raw = result.text
    if not raw:
        raise ValueError("Judge returned an empty response.")

    score = float(json.loads(raw)["score"])
    if score not in {0.0, 0.5, 1.0}:
        raise ValueError(f"Judge score must be 0, 0.5, or 1, got {score}.")
    return score


dataset = [
    {"inputs": {"query": "I was charged $24.50 but I thought that was refunded?"}},
    {"inputs": {"query": "What's my current account balance?"}},
    {"inputs": {"query": "Show me my recent charges."}},
    {"inputs": {"query": "The export button gives me error 500."}},
    {"inputs": {"query": "Our API calls are getting rate limited. How do we increase the limit?"}},
]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", choices=["v1", "v2"], default="v2")
    args = parser.parse_args()

    agent_mod = load_agent_module(args.version)

    result = evaluate(
        function=make_run_support_agent(agent_mod.build_agents),
        dataset=dataset,
        evaluators=[response_quality],
        instrumentors=[
            lambda: GoogleADKInstrumentor(),
        ],
        name=f"customer-support-eval-{args.version}",
    )

    print(f"Version:   {args.version}")
    print(f"Run ID:    {result.run_id}")
    print("View aggregate scores and traces in HoneyHive: https://app.honeyhive.ai")
