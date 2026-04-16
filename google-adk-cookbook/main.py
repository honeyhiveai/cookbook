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
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part
from openinference.instrumentation.google_adk import GoogleADKInstrumentor

from honeyhive import HoneyHiveTracer, trace

load_dotenv()

MODEL = LiteLlm(model="openai/gpt-5.4-mini")
APP_NAME = "customer-support-cookbook"
USER_ID = "customer_42"
CUSTOMER_DB = {
    USER_ID: {"plan": "enterprise", "billing_customer_id": "CUST-2048"},
}


def lookup_billing(customer_id: str, query_type: str) -> dict:
    """Look up billing information for a customer."""
    if query_type == "balance":
        return {"customer_id": customer_id, "balance": "$1,247.50", "due": "2026-03-01"}
    if query_type == "refund_status":
        return {"customer_id": customer_id, "refund_id": "REF-2026-0142", "amount": "$24.50", "status": "processing"}
    return {"error": f"Unknown query type: {query_type}"}


def search_knowledge_base(issue: str) -> dict:
    """Search the technical knowledge base for solutions to product issues."""
    issue = issue.lower()
    if "export" in issue:
        return {"article_id": "KB-1042", "solution": "Clear browser cache and retry. Free-plan exports are capped at 10k rows."}
    if "api" in issue:
        return {"article_id": "KB-0891", "solution": "Default rate limit is 100 req/min. Enterprise gets 1000 req/min."}
    if "login" in issue:
        return {"article_id": "KB-0567", "solution": "Reset at /reset-password. For SSO, check Settings > SSO."}
    return {"article_id": "KB-0001", "solution": "Please provide more details."}


def build_agents() -> LlmAgent:
    """Build the multi-agent customer support system."""
    billing_agent = LlmAgent(
        name="billing_agent",
        model=MODEL,
        description="Handles billing: balances, charges, refund status, invoices.",
        instruction=(
            "You are a billing support specialist. "
            "Use lookup_billing for balances, charges, or refunds. "
            "Summarize the result with amounts, dates, and the next step."
        ),
        tools=[lookup_billing],
    )
    technical_agent = LlmAgent(
        name="technical_agent",
        model=MODEL,
        description="Handles product bugs, API questions, and general troubleshooting.",
        instruction=(
            "You are a technical support specialist. "
            "Use search_knowledge_base for bugs, exports, login, and API questions. "
            "Respond with concrete troubleshooting steps."
        ),
        tools=[search_knowledge_base],
    )
    return LlmAgent(
        name="customer_support",
        model=MODEL,
        description="Routes customer support requests to the right specialist.",
        instruction=(
            "You are the front-line customer support coordinator. "
            "Delegate billing issues to billing_agent; product, login, export, and API issues to technical_agent. "
            "Do not answer specialist questions yourself — always delegate first, then return a concise final response."
        ),
        sub_agents=[billing_agent, technical_agent],
    )


# @trace() captures this app-layer function as a custom HoneyHive span,
# so it shows up alongside the auto-instrumented ADK spans.
@trace()
def load_customer_context(customer_id: str) -> dict:
    """Load customer context from the application data store."""
    return CUSTOMER_DB.get(customer_id, {"plan": "unknown", "billing_customer_id": customer_id})


def build_agent_input(query: str, customer_id: str) -> str:
    """Prepend customer context to the raw query before sending it to ADK."""
    ctx = load_customer_context(customer_id)
    return (
        f"Customer context: user_id={customer_id}, plan={ctx['plan']}, "
        f"billing_customer_id={ctx['billing_customer_id']}\n\n"
        f"Customer request: {query.strip()}"
    )


async def handle_customer_query(
    runner: Runner, session_id: str, query: str
) -> tuple[str, list[str]]:
    """Send a query to the support agent.

    Returns the final response text and the list of ADK event authors
    (used by `evaluate.py` to verify which specialist handled the query).
    """
    msg = Content(role="user", parts=[Part(text=build_agent_input(query, USER_ID))])

    response_text = ""
    event_authors: list[str] = []
    async for event in runner.run_async(
        user_id=USER_ID, session_id=session_id, new_message=msg
    ):
        author = getattr(event, "author", None)
        if isinstance(author, str):
            event_authors.append(author)
        if event.is_final_response() and event.content and event.content.parts:
            response_text = event.content.parts[0].text or ""
    return response_text, event_authors


async def main() -> None:
    """Run the tracing demo."""
    # --- HoneyHive setup (3 lines) ---
    tracer = HoneyHiveTracer.init(
        api_key=os.getenv("HH_API_KEY"),
        project=os.getenv("HH_PROJECT"),
        session_name="customer-support",
        source="cookbook",
    )
    GoogleADKInstrumentor().instrument(tracer_provider=tracer.provider)
    tracer.enrich_session(
        user_properties={"user_id": USER_ID, "plan": "enterprise"},
        metadata={"environment": os.getenv("HH_ENV", "local"), "app_version": "2.1.0"},
    )

    # --- ADK app (unchanged by HoneyHive) ---
    try:
        session_service = InMemorySessionService()
        runner = Runner(
            agent=build_agents(), app_name=APP_NAME, session_service=session_service
        )
        await session_service.create_session(
            app_name=APP_NAME, user_id=USER_ID, session_id=tracer.session_id
        )

        query = "I was charged $24.50 last week but I thought that was supposed to be refunded?"
        print(f"Customer: {query}")
        response, _ = await handle_customer_query(runner, tracer.session_id, query)
        print(f"Agent:    {response}")
        print(f"Session ID: {tracer.session_id}")
    finally:
        tracer.flush()


if __name__ == "__main__":
    asyncio.run(main())
