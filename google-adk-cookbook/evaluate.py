"""
Evaluate the customer support agent using HoneyHive experiments.

Run:
    uv run python evaluate.py
"""

import re
import uuid

from dotenv import load_dotenv
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part
from openai import OpenAI

from honeyhive import evaluate

from main import APP_NAME, USER_ID, build_agent_input, build_agents, extract_text

load_dotenv()

openai_client = OpenAI()
SPECIALIST_CATEGORIES = {
    "billing_agent": "billing",
    "technical_agent": "technical",
}
SCORE_PATTERN = re.compile(r"\b(?:0(?:\.\d+)?|1(?:\.0+)?)\b")


def get_query(datapoint: dict) -> str:
    """Validate and return the customer query from an eval datapoint."""
    inputs = datapoint.get("inputs")
    if not isinstance(inputs, dict):
        raise ValueError("Datapoint must include an 'inputs' dictionary.")

    query = inputs.get("query")
    if not isinstance(query, str) or not query.strip():
        raise ValueError("Datapoint must include a non-empty 'inputs.query' string.")

    return query.strip()


def parse_judge_score(raw_score: str | None) -> float:
    """Extract a 0.0-1.0 score from an LLM judge response."""
    if not raw_score:
        raise ValueError("Judge returned an empty score.")

    match = SCORE_PATTERN.search(raw_score)
    if match is None:
        raise ValueError(f"Judge did not return a numeric score: {raw_score!r}")

    score = float(match.group(0))
    if not 0.0 <= score <= 1.0:
        raise ValueError(f"Judge score must be between 0.0 and 1.0, got {score}.")
    return score


def detect_specialist(authors: list[str]) -> str:
    """Infer which specialist handled the request from ADK event authors."""
    specialists = [author for author in authors if author in SPECIALIST_CATEGORIES]
    unique_specialists = list(dict.fromkeys(specialists))

    if len(unique_specialists) == 1:
        return unique_specialists[0]
    if len(unique_specialists) > 1:
        return "multiple"
    return "unknown"


async def run_support_agent(datapoint: dict) -> dict:
    """Run the support agent on a single datapoint."""
    query = get_query(datapoint)

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
        if event.is_final_response():
            response_text = extract_text(event.content)

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
        messages=[
            {
                "role": "system",
                "content": (
                    "You evaluate customer support responses.\n"
                    "Score the response from 0.0 to 1.0 based on:\n"
                    "- whether it answers the question\n"
                    "- whether it is accurate for the expected category\n"
                    "- whether the tone is professional and helpful\n\n"
                    "Reply with only a number between 0.0 and 1.0."
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
    return parse_judge_score(result.choices[0].message.content)


def correct_routing(outputs: dict, inputs: dict, ground_truth: dict) -> float:
    """Check whether ADK delegated the query to the expected specialist."""
    handled_by = outputs.get("handled_by")
    if handled_by not in SPECIALIST_CATEGORIES:
        raise ValueError(
            "Could not determine a single delegated specialist from ADK events. "
            f"Observed authors: {outputs.get('event_authors', [])!r}"
        )

    expected_category = ground_truth["category"]
    observed_category = SPECIALIST_CATEGORIES[handled_by]
    return 1.0 if observed_category == expected_category else 0.0


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
        name="customer-support-eval",
    )

    print(f"\nExperiment run_id: {result.run_id}")
    print("View results in HoneyHive: https://app.honeyhive.ai")
    print("=" * 60)
