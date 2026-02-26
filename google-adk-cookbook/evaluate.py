"""
Evaluate the customer support agent using HoneyHive experiments.

Runs the multi-agent support bot against a test dataset and measures
response quality with an LLM evaluator.

Run: python evaluate.py
"""

import os

from dotenv import load_dotenv

load_dotenv()

from honeyhive import evaluate
from openai import OpenAI

from main import build_agents

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part


# ---------------------------------------------------------------
# 1. Task function: run the agent on a single datapoint
# ---------------------------------------------------------------

async def run_support_agent(datapoint):
    """Run the support agent on a single datapoint.

    Called once per dataset row by HoneyHive's evaluate().
    Receives a dict with 'inputs' and 'ground_truth' keys.
    Returns a dict of outputs to pass to evaluators.
    """
    query = datapoint["inputs"]["query"]

    coordinator = build_agents()
    session_service = InMemorySessionService()
    session_id = f"eval-{id(datapoint):x}"

    await session_service.create_session(
        app_name="support-eval",
        user_id="eval_user",
        session_id=session_id,
    )

    runner = Runner(
        agent=coordinator,
        app_name="support-eval",
        session_service=session_service,
    )

    msg = Content(role="user", parts=[Part(text=query)])
    response_text = ""
    async for event in runner.run_async(
        user_id="eval_user",
        session_id=session_id,
        new_message=msg,
    ):
        if event.is_final_response() and event.content and event.content.parts:
            response_text = event.content.parts[0].text

    return {"response": response_text}


# ---------------------------------------------------------------
# 2. Evaluators
# ---------------------------------------------------------------

openai_client = OpenAI()


def response_quality(outputs, inputs, ground_truth):
    """Use an LLM to judge whether the agent response is helpful and correct."""
    try:
        result = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You evaluate customer support responses. "
                        "Score the response from 0.0 to 1.0 based on:\n"
                        "- Did it address the customer's question?\n"
                        "- Is the information accurate given the expected category?\n"
                        "- Is the tone professional and helpful?\n\n"
                        "Reply with ONLY a number between 0.0 and 1.0."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Customer query: {inputs['query']}\n"
                        f"Expected category: {ground_truth['category']}\n"
                        f"Agent response: {outputs['response']}"
                    ),
                },
            ],
            temperature=0,
        )
        return float(result.choices[0].message.content.strip())
    except (ValueError, Exception):
        return 0.0


def correct_routing(outputs, inputs, ground_truth):
    """Use an LLM to check if the query was routed to the right specialist."""
    try:
        result = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You evaluate whether a customer support query was handled by the "
                        "correct specialist. The two specialists are:\n"
                        "- billing: handles charges, refunds, invoices, account balances\n"
                        "- technical: handles bugs, errors, features, API issues, troubleshooting\n\n"
                        "Based on the query and the response, determine if the response came "
                        "from the correct specialist for the expected category.\n\n"
                        "Reply with ONLY 1.0 (correct routing) or 0.0 (wrong routing)."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Customer query: {inputs['query']}\n"
                        f"Expected category: {ground_truth['category']}\n"
                        f"Agent response: {outputs['response']}"
                    ),
                },
            ],
            temperature=0,
        )
        return float(result.choices[0].message.content.strip())
    except (ValueError, Exception):
        return 0.0


# ---------------------------------------------------------------
# 3. Test dataset
# ---------------------------------------------------------------

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


# ---------------------------------------------------------------
# 4. Run the experiment
# ---------------------------------------------------------------

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
