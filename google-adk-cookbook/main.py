"""
Multi-agent customer support app with HoneyHive observability.

A coordinator agent routes customer queries to specialist sub-agents:
  - billing_agent: handles charges, refunds, invoices
  - technical_agent: handles product issues, troubleshooting

Run:
    uv run python main.py
"""

import asyncio
import os

from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part
from openinference.instrumentation.google_adk import GoogleADKInstrumentor

from honeyhive import HoneyHiveTracer, trace

load_dotenv()

MODEL = "gemini-2.5-flash"
APP_NAME = "customer-support-cookbook"
USER_ID = "customer_42"
CUSTOMER_DB = {
    USER_ID: {
        "billing_customer_id": "CUST-2048",
        "plan": "enterprise",
        "support_tier": "priority",
        "account_status": "active",
        "region": "us-east-1",
    }
}


def lookup_billing(customer_id: str, query_type: str) -> dict:
    """Look up billing information for a customer."""
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
    """Search the technical knowledge base for solutions to product issues."""
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
            "support up to 1,000 requests/minute. Add exponential backoff to your client.",
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
        "solution": "Please provide more details about your issue so we can help.",
        "article_id": "KB-0001",
    }


def build_agents() -> LlmAgent:
    """Build the multi-agent customer support system."""
    billing_agent = LlmAgent(
        name="billing_agent",
        model=MODEL,
        description=(
            "Handles billing inquiries including balances, recent charges, "
            "refund status, invoices, and payment questions."
        ),
        instruction=(
            "You are a billing support specialist.\n"
            "Use the lookup_billing tool for account balances, charges, or refunds.\n"
            "Summarize the result clearly with amounts, dates, and the next step.\n"
            "If the customer has not provided a customer ID, ask for it."
        ),
        tools=[lookup_billing],
    )

    technical_agent = LlmAgent(
        name="technical_agent",
        model=MODEL,
        description=(
            "Handles product bugs, feature questions, API issues, and general troubleshooting."
        ),
        instruction=(
            "You are a technical support specialist.\n"
            "Use the search_knowledge_base tool for bugs, errors, export issues, login problems, "
            "and API questions.\n"
            "Respond with concrete troubleshooting steps and note when an issue may need escalation."
        ),
        tools=[search_knowledge_base],
    )

    return LlmAgent(
        name="customer_support",
        model=MODEL,
        description="Routes customer support requests to the right specialist.",
        instruction=(
            "You are the front-line customer support coordinator.\n"
            "Delegate billing issues to billing_agent.\n"
            "Delegate product bugs, login issues, exports, and API questions to technical_agent.\n"
            "Do not answer specialist questions yourself. Always delegate first and then return a concise final response."
        ),
        sub_agents=[billing_agent, technical_agent],
    )


def extract_text(content: Content | None) -> str:
    """Return only text parts from an ADK content payload."""
    if not content or not getattr(content, "parts", None):
        return ""
    text_parts = [part.text for part in content.parts if getattr(part, "text", None)]
    return "\n".join(text_parts).strip()


# HoneyHive custom spans are useful for your own app-layer work outside ADK,
# like loading customer records before handing a request to the agent.
@trace()
def load_customer_context(customer_id: str) -> dict:
    """Load customer context from the application data store."""
    return CUSTOMER_DB.get(
        customer_id,
        {
            "billing_customer_id": customer_id,
            "plan": "unknown",
            "support_tier": "standard",
            "account_status": "unknown",
            "region": "unknown",
        },
    )


def build_agent_input(query: str, customer_id: str) -> str:
    """Combine the raw query with customer context before sending it to ADK."""
    customer_context = load_customer_context(customer_id)
    return (
        "Authenticated customer context:\n"
        f"- internal_user_id: {customer_id}\n"
        f"- billing_customer_id: {customer_context['billing_customer_id']}\n"
        f"- plan: {customer_context['plan']}\n"
        f"- support_tier: {customer_context['support_tier']}\n"
        f"- account_status: {customer_context['account_status']}\n"
        f"- region: {customer_context['region']}\n\n"
        "Use this context when it helps answer the request. "
        "Do not repeat internal metadata unless it is relevant.\n\n"
        f"Customer request: {query.strip()}"
    )


async def handle_customer_query(runner: Runner, session_id: str, query: str) -> str:
    """Send a query to the support agent and return the final response text."""
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
    return response_text


async def main() -> None:
    """Run the tracing demo."""
    tracer = HoneyHiveTracer.init(
        api_key=os.getenv("HH_API_KEY"),
        project=os.getenv("HH_PROJECT"),
        session_name="customer-support",
        source="cookbook",
    )
    instrumentor = GoogleADKInstrumentor()
    tracer_provider = getattr(tracer, "provider", None)
    if tracer_provider is not None:
        instrumentor.instrument(tracer_provider=tracer_provider)
    else:
        instrumentor.instrument()
    session_service = InMemorySessionService()

    try:
        tracer.enrich_session(
            user_properties={
                "user_id": USER_ID,
                "plan": "enterprise",
            },
            metadata={
                "environment": os.getenv("HH_ENV", "local"),
                "app_version": "2.1.0",
            },
        )

        coordinator = build_agents()
        runner = Runner(
            agent=coordinator,
            app_name=APP_NAME,
            session_service=session_service,
        )
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
                app_name=APP_NAME,
                user_id=USER_ID,
                session_id=session_id,
            )

            print(f"\nCustomer: {query}")
            response = await handle_customer_query(runner, session_id, query)
            preview = response[:200]
            suffix = "..." if len(response) > 200 else ""
            print(f"Agent:    {preview}{suffix}")

        print("\n" + "=" * 60)
        print(f"Session ID: {tracer.session_id}")
        print("Check HoneyHive dashboard for traces.")
        print("=" * 60)
    finally:
        flush = getattr(tracer, "force_flush", None) or getattr(tracer, "flush", None)
        if callable(flush):
            flush()
        instrumentor.uninstrument()


if __name__ == "__main__":
    asyncio.run(main())
