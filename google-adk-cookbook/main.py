"""
Multi-agent customer support app with HoneyHive observability.

A coordinator agent routes customer queries to specialist sub-agents:
  - billing_agent: handles charges, refunds, invoices
  - technical_agent: handles product issues, troubleshooting

Run: python main.py
"""

import asyncio
import os

from dotenv import load_dotenv

load_dotenv()

from honeyhive import HoneyHiveTracer, trace
from openinference.instrumentation.google_adk import GoogleADKInstrumentor

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part


# ---------------------------------------------------------------
# Tools (mock implementations for the cookbook)
# ---------------------------------------------------------------

def lookup_billing(customer_id: str, query_type: str) -> dict:
    """Look up billing information for a customer.

    Args:
        customer_id: The customer's account ID.
        query_type: Type of billing query - one of 'balance', 'charges', 'refund_status'.
    """
    records = {
        "balance": {
            "customer_id": customer_id,
            "current_balance": "$1,247.50",
            "due_date": "2026-03-01",
            "status": "current",
        },
        "charges": {
            "customer_id": customer_id,
            "recent_charges": [
                {"date": "2026-02-01", "amount": "$99.00", "description": "Monthly subscription"},
                {"date": "2026-02-05", "amount": "$24.50", "description": "API overage"},
            ],
        },
        "refund_status": {
            "customer_id": customer_id,
            "refund_id": "REF-2026-0142",
            "amount": "$24.50",
            "status": "processing",
            "estimated_completion": "2026-02-20",
        },
    }
    return records.get(query_type, {"error": f"Unknown query type: {query_type}"})


def search_knowledge_base(issue: str) -> dict:
    """Search the technical knowledge base for solutions to product issues.

    Args:
        issue: Description of the technical issue or product question.
    """
    solutions = {
        "export": {
            "title": "Export Feature - Error 500",
            "solution": "Clear browser cache and retry. If the issue persists, check that "
            "your dataset is under 10,000 rows (the export limit for free plans).",
            "article_id": "KB-1042",
        },
        "api": {
            "title": "API Rate Limiting",
            "solution": "The default rate limit is 100 requests/minute. Enterprise plans "
            "support up to 1,000 req/min. Add exponential backoff to your client.",
            "article_id": "KB-0891",
        },
        "login": {
            "title": "Login / Authentication Issues",
            "solution": "Try resetting your password at /reset-password. If using SSO, "
            "confirm your identity provider is configured correctly in Settings > SSO.",
            "article_id": "KB-0567",
        },
    }
    issue_lower = issue.lower()
    for keyword, article in solutions.items():
        if keyword in issue_lower:
            return article
    return {
        "title": "General Troubleshooting",
        "solution": "Please provide more details about your issue so we can help. "
        "You can also check docs.example.com for guides.",
        "article_id": "KB-0001",
    }


# ---------------------------------------------------------------
# Agent definitions
# ---------------------------------------------------------------

def build_agents() -> Agent:
    """Build the multi-agent customer support system.

    Returns the top-level coordinator agent with specialist sub-agents attached.
    Importable by evaluate.py without triggering side effects.
    """
    billing_agent = Agent(
        name="billing_agent",
        model="gemini-2.0-flash",
        description="Handles billing inquiries including account balances, recent charges, "
        "invoice questions, and refund status. Routes here for any money-related questions.",
        instruction=(
            "You are a billing support specialist. Help customers with their billing questions. "
            "Use the lookup_billing tool to find account information. "
            "Be clear about amounts, dates, and next steps. "
            "Always address the customer politely and confirm what action was taken."
        ),
        tools=[lookup_billing],
    )

    technical_agent = Agent(
        name="technical_agent",
        model="gemini-2.0-flash",
        description="Handles technical support including product bugs, feature questions, "
        "error messages, API issues, and troubleshooting. Routes here for any product-related questions.",
        instruction=(
            "You are a technical support specialist. Help customers resolve product issues. "
            "Use the search_knowledge_base tool to find relevant solutions. "
            "Provide step-by-step instructions when possible. "
            "If the issue needs escalation, let the customer know."
        ),
        tools=[search_knowledge_base],
    )

    coordinator = Agent(
        name="customer_support",
        model="gemini-2.0-flash",
        description="Customer support coordinator that routes queries to specialists.",
        instruction=(
            "You are the front-line customer support coordinator. "
            "Analyze each customer message and route it to the right specialist:\n"
            "- billing_agent: for charges, invoices, refunds, account balances, payments\n"
            "- technical_agent: for bugs, errors, features, API issues, troubleshooting\n\n"
            "Do NOT try to answer questions yourself. Always delegate to a specialist."
        ),
        sub_agents=[billing_agent, technical_agent],
    )

    return coordinator


# ---------------------------------------------------------------
# Custom span for input preprocessing
# ---------------------------------------------------------------

@trace()
def preprocess_query(raw_query: str) -> str:
    """Normalize and validate customer input before sending to the agent."""
    cleaned = raw_query.strip()
    if len(cleaned) < 3:
        return "Could you please provide more details about your question?"
    return cleaned


# ---------------------------------------------------------------
# Query handler
# ---------------------------------------------------------------

async def handle_customer_query(runner, session_id: str, query: str) -> str:
    """Send a query to the support agent and return the response."""
    processed = preprocess_query(query)
    msg = Content(role="user", parts=[Part(text=processed)])

    response_text = ""
    async for event in runner.run_async(
        user_id="customer_42",
        session_id=session_id,
        new_message=msg,
    ):
        if event.is_final_response() and event.content and event.content.parts:
            response_text = event.content.parts[0].text
    return response_text


# ---------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------

async def main():
    # 1. Initialize HoneyHive tracing
    tracer = HoneyHiveTracer.init(
        api_key=os.getenv("HH_API_KEY"),
        project=os.getenv("HH_PROJECT"),
        session_name="customer-support",
        source="cookbook",
    )
    instrumentor = GoogleADKInstrumentor()
    instrumentor.instrument(tracer_provider=tracer.provider)

    try:
        # 2. Enrich session with business context
        tracer.enrich_session(
            user_properties={
                "user_id": "customer_42",
                "plan": "enterprise",
            },
            metadata={
                "environment": "production",
                "app_version": "2.1.0",
            },
        )

        # 3. Build agents and session service
        coordinator = build_agents()
        session_service = InMemorySessionService()

        # 4. Run sample queries
        queries = [
            "I was charged $24.50 last week but I thought that was supposed to be refunded?",
            "The export button gives me an error 500 when I try to download my data.",
            "What's my current account balance?",
        ]

        print("=" * 60)
        print("Customer Support Agent (Google ADK + HoneyHive)")
        print("=" * 60)

        for i, query in enumerate(queries):
            session_id = f"{tracer.session_id}-{i}"
            await session_service.create_session(
                app_name="support-app",
                user_id="customer_42",
                session_id=session_id,
            )
            runner = Runner(
                agent=coordinator,
                app_name="support-app",
                session_service=session_service,
            )

            print(f"\nCustomer: {query}")
            response = await handle_customer_query(runner, session_id, query)
            print(f"Agent:    {response[:200]}{'...' if len(response) > 200 else ''}")

        print("\n" + "=" * 60)
        print(f"Session ID: {tracer.session_id}")
        print("Check HoneyHive dashboard for traces!")
        print("=" * 60)

    finally:
        tracer.force_flush()
        instrumentor.uninstrument()


if __name__ == "__main__":
    asyncio.run(main())
