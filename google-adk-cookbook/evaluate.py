"""
Evaluate the customer support agent using HoneyHive experiments.

Run:
    uv run python evaluate.py
"""

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


async def run_support_agent(datapoint: dict) -> dict:
    """Run the support agent on a single datapoint."""
    query = datapoint["inputs"]["query"]

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
    async for event in runner.run_async(
        user_id=USER_ID,
        session_id=session_id,
        new_message=msg,
    ):
        if event.is_final_response():
            response_text = extract_text(event.content)

    return {"response": response_text}


def response_quality(outputs: dict, inputs: dict, ground_truth: dict) -> float:
    """Judge whether the response is accurate, helpful, and appropriately toned."""
    try:
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
        return float(result.choices[0].message.content.strip())
    except Exception:
        return 0.0


def correct_routing(outputs: dict, inputs: dict, ground_truth: dict) -> float:
    """Judge whether the query reached the right specialist."""
    try:
        result = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You judge specialist routing for a customer support system.\n"
                        "The available specialists are:\n"
                        "- billing: charges, balances, invoices, refunds, payments\n"
                        "- technical: bugs, login problems, exports, APIs, troubleshooting\n\n"
                        "Based on the query and response, decide whether the response came from "
                        "the correct specialist for the expected category.\n"
                        "Reply with only 1.0 for correct routing or 0.0 for incorrect routing."
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
        return float(result.choices[0].message.content.strip())
    except Exception:
        return 0.0


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
