"""
Multi-agent customer support demo with HoneyHive observability.

Picks either the initial (v1) or improved (v2) agent via --version.

Run:
    uv run python main.py --version v1
    uv run python main.py --version v2
"""

import argparse
import asyncio
import importlib
import os

from dotenv import load_dotenv
from google.adk.agents.invocation_context import LlmCallsLimitExceededError
from google.adk.agents.run_config import RunConfig
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part
from openinference.instrumentation.google_adk import GoogleADKInstrumentor

from honeyhive import HoneyHiveTracer, trace

load_dotenv(override=True)

APP_NAME = "customer-support-cookbook"
USER_ID = "customer_42"
CUSTOMER_DB = {
    USER_ID: {"plan": "enterprise", "billing_customer_id": "CUST-2048"},
}
# Cap LLM calls per query so a confused agent fails fast instead of looping.
RUN_CONFIG = RunConfig(max_llm_calls=15)


def load_agent_module(version: str):
    """Import the agent module for the requested version ("v1" or "v2")."""
    if version not in {"v1", "v2"}:
        raise ValueError(f"Unknown version {version!r}. Expected 'v1' or 'v2'.")
    return importlib.import_module(f"agent_{version}")


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
) -> str:
    """Send a query to the support agent and return the final response text."""
    msg = Content(role="user", parts=[Part(text=build_agent_input(query, USER_ID))])

    response_text = ""
    try:
        async for event in runner.run_async(
            user_id=USER_ID,
            session_id=session_id,
            new_message=msg,
            run_config=RUN_CONFIG,
        ):
            if event.is_final_response() and event.content and event.content.parts:
                response_text = event.content.parts[0].text or ""
    except LlmCallsLimitExceededError:
        response_text = "[agent gave up: exceeded max LLM calls without producing a final response]"
    return response_text


async def main(version: str) -> None:
    """Run the tracing demo against the selected agent version."""
    agent_mod = load_agent_module(version)

    tracer = HoneyHiveTracer.init(
        api_key=os.getenv("HH_API_KEY"),
        project=os.getenv("HH_PROJECT"),
        session_name=f"customer-support-{version}",
        source="cookbook",
    )
    GoogleADKInstrumentor().instrument(tracer_provider=tracer.provider)
    tracer.enrich_session(
        user_properties={"user_id": USER_ID, "plan": "enterprise"},
        metadata={"environment": os.getenv("HH_ENV", "local"), "agent_version": version},
    )

    try:
        session_service = InMemorySessionService()
        runner = Runner(
            agent=agent_mod.build_agents(),
            app_name=APP_NAME,
            session_service=session_service,
        )
        await session_service.create_session(
            app_name=APP_NAME, user_id=USER_ID, session_id=tracer.session_id
        )

        query = "I was charged $24.50 last week but I thought that was supposed to be refunded?"
        print(f"Version:  {version}")
        print(f"Customer: {query}")
        response = await handle_customer_query(runner, tracer.session_id, query)
        print(f"Agent:    {response}")
        print(f"Session ID: {tracer.session_id}")
    finally:
        tracer.flush()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", choices=["v1", "v2"], default="v2")
    args = parser.parse_args()
    asyncio.run(main(args.version))
