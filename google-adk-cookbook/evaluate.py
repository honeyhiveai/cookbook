"""
Evaluate the customer support agent using HoneyHive experiments.

Run:
    uv run python evaluate.py
"""

import json
import uuid

from dotenv import load_dotenv
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from openai import OpenAI
from openinference.instrumentation.google_adk import GoogleADKInstrumentor
from openinference.instrumentation.openai import OpenAIInstrumentor

from honeyhive import evaluate

from main import APP_NAME, USER_ID, build_agents, handle_customer_query

load_dotenv()

openai_client = OpenAI()

ROUTES = {"billing_agent": "billing", "technical_agent": "technical"}


def detect_specialist(authors: list[str]) -> str:
    """Infer which specialist handled the request from ADK event authors."""
    found = {ROUTES[a] for a in authors if a in ROUTES}
    if len(found) == 1:
        return found.pop()
    return "multiple" if found else "unknown"


async def run_support_agent(datapoint: dict) -> dict:
    """Run the support agent on a single datapoint."""
    session_service = InMemorySessionService()
    session_id = f"eval-{uuid.uuid4().hex[:12]}"
    await session_service.create_session(
        app_name=f"{APP_NAME}-eval", user_id=USER_ID, session_id=session_id
    )
    runner = Runner(
        agent=build_agents(),
        app_name=f"{APP_NAME}-eval",
        session_service=session_service,
    )

    response, authors = await handle_customer_query(
        runner, session_id, datapoint["inputs"]["query"]
    )
    return {
        "response": response,
        "handled_by": detect_specialist(authors),
        "event_authors": authors,
    }


def response_quality(outputs: dict, inputs: dict, ground_truth: dict) -> float:
    """Judge whether the response is accurate, helpful, and appropriately toned."""
    result = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": 'Score customer support responses 0.0-1.0 on accuracy, helpfulness, and tone. Return {"score": <number>}.',
            },
            {
                "role": "user",
                "content": (
                    f"Customer query: {inputs['query']}\n"
                    f"Expected category: {ground_truth['category']}\n"
                    f"Agent response: {outputs.get('response', '')}"
                ),
            },
        ],
    )
    raw = result.choices[0].message.content
    if not raw:
        raise ValueError("Judge returned an empty response.")

    score = float(json.loads(raw)["score"])
    if not 0.0 <= score <= 1.0:
        raise ValueError(f"Judge score must be between 0.0 and 1.0, got {score}.")
    return score


def correct_routing(outputs: dict, inputs: dict, ground_truth: dict) -> float:
    """Check whether ADK delegated the query to the expected specialist."""
    handled_by = outputs.get("handled_by")
    if handled_by not in {"billing", "technical"}:
        raise ValueError(
            "Could not determine a single delegated specialist from ADK events. "
            f"Observed authors: {outputs.get('event_authors', [])!r}"
        )
    return 1.0 if handled_by == ground_truth["category"] else 0.0


dataset = [
    {"inputs": {"query": "I was charged $24.50 but I thought that was refunded?"}, "ground_truth": {"category": "billing"}},
    {"inputs": {"query": "What's my current account balance?"}, "ground_truth": {"category": "billing"}},
    {"inputs": {"query": "The export button gives me error 500."}, "ground_truth": {"category": "technical"}},
    {"inputs": {"query": "Our API calls are getting rate limited. How do we increase the limit?"}, "ground_truth": {"category": "technical"}},
]


if __name__ == "__main__":
    result = evaluate(
        function=run_support_agent,
        dataset=dataset,
        evaluators=[response_quality, correct_routing],
        instrumentors=[
            lambda: GoogleADKInstrumentor(),
            lambda: OpenAIInstrumentor(),
        ],
        name="customer-support-eval",
    )

    print(f"Experiment run_id: {result.run_id}")
    print("View results in HoneyHive: https://app.honeyhive.ai")
