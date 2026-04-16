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
from google.genai.types import Content, Part
from openai import OpenAI
from openinference.instrumentation.google_adk import GoogleADKInstrumentor
from openinference.instrumentation.openai import OpenAIInstrumentor

from honeyhive import evaluate

from main import APP_NAME, USER_ID, build_agent_input, build_agents

load_dotenv()

openai_client = OpenAI()


def detect_specialist(authors: list[str]) -> str:
    """Infer which specialist handled the request from ADK event authors."""
    specialists = []
    for author in authors:
        if author == "billing_agent":
            specialists.append("billing")
        elif author == "technical_agent":
            specialists.append("technical")
    unique_specialists = list(dict.fromkeys(specialists))

    if len(unique_specialists) == 1:
        return unique_specialists[0]
    if len(unique_specialists) > 1:
        return "multiple"
    return "unknown"


async def run_support_agent(datapoint: dict) -> dict:
    """Run the support agent on a single datapoint."""
    query = datapoint["inputs"]["query"].strip()

    coordinator = build_agents()
    session_service = InMemorySessionService()
    session_id = f"eval-{uuid.uuid4().hex[:12]}"

    await session_service.create_session(
        app_name=f"{APP_NAME}-eval",
        user_id=USER_ID,
        session_id=session_id,
    )

    runner = Runner(
        agent=coordinator,
        app_name=f"{APP_NAME}-eval",
        session_service=session_service,
    )

    agent_input = build_agent_input(query, USER_ID)
    msg = Content(role="user", parts=[Part(text=agent_input)])
    response_text = ""
    event_authors: list[str] = []
    async for event in runner.run_async(
        user_id=USER_ID,
        session_id=session_id,
        new_message=msg,
    ):
        author = getattr(event, "author", None)
        if isinstance(author, str):
            event_authors.append(author)
        if event.is_final_response() and event.content and event.content.parts:
            response_text = event.content.parts[0].text or ""

    return {
        "response": response_text,
        "handled_by": detect_specialist(event_authors),
        "event_authors": event_authors,
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
                "content": (
                    "You evaluate customer support responses.\n"
                    "Score the response from 0.0 to 1.0 based on:\n"
                    "- whether it answers the question\n"
                    "- whether it is accurate for the expected category\n"
                    "- whether the tone is professional and helpful\n\n"
                    'Respond with JSON of the form {"score": <number between 0.0 and 1.0>}.'
                ),
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
    {
        "inputs": {"query": "I was charged $24.50 but I thought that was refunded?"},
        "ground_truth": {"category": "billing"},
    },
    {
        "inputs": {"query": "What's my current account balance?"},
        "ground_truth": {"category": "billing"},
    },
    {
        "inputs": {"query": "Can you show me my recent charges for this month?"},
        "ground_truth": {"category": "billing"},
    },
    {
        "inputs": {"query": "The export button gives me error 500."},
        "ground_truth": {"category": "technical"},
    },
    {
        "inputs": {"query": "I can't log in. The password reset email never arrived."},
        "ground_truth": {"category": "technical"},
    },
    {
        "inputs": {"query": "Our API calls are getting rate limited. How do we increase the limit?"},
        "ground_truth": {"category": "technical"},
    },
    {
        "inputs": {"query": "I need a refund for the duplicate charge on Feb 5th."},
        "ground_truth": {"category": "billing"},
    },
    {
        "inputs": {"query": "How do I export data from the dashboard? It keeps failing."},
        "ground_truth": {"category": "technical"},
    },
]


if __name__ == "__main__":
    print("=" * 60)
    print("Customer Support Agent - Evaluation")
    print("=" * 60)

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

    print(f"\nExperiment run_id: {result.run_id}")
    print("View results in HoneyHive: https://app.honeyhive.ai")
    print("=" * 60)
