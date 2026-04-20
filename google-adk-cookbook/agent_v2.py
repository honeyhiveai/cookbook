"""
Improved (v2) customer support agent.

Same tool implementations and opaque enum codes as `agent_v1.py`, but with:
  - Detailed tool docstrings that document every enum value.
  - Descriptive sub-agent descriptions so the coordinator routes correctly.
  - An explicit delegation rule in the coordinator's instruction.

Nothing about the code logic changed. Every improvement is in what the model
sees about the tools and agents. This is the "after" state.
"""

from google.adk.agents import LlmAgent

MODEL = "gemini-flash-latest"


def lookup_billing(customer_id: str, query_type: str) -> dict:
    """Look up billing information for a customer.

    Args:
        customer_id: The internal user id of the customer (e.g. "customer_42").
        query_type: One of:
            - "BIL_ACCT_01": current account balance and due date
            - "BIL_TXN_02": recent charges on the account
            - "BIL_RMA_03": status of an in-flight refund

    Returns:
        A dict with the requested billing fields, or {"error": ...} if
        query_type is not one of the supported enum codes above.
    """
    if query_type == "BIL_ACCT_01":
        return {"customer_id": customer_id, "balance": "$1,247.50", "due": "2026-03-01"}
    if query_type == "BIL_TXN_02":
        return {
            "customer_id": customer_id,
            "recent_charges": [
                {"date": "2026-02-01", "amount": "$99.00", "description": "Monthly subscription"},
                {"date": "2026-02-05", "amount": "$24.50", "description": "API overage"},
            ],
        }
    if query_type == "BIL_RMA_03":
        return {"customer_id": customer_id, "refund_id": "REF-2026-0142", "amount": "$24.50", "status": "processing"}
    return {"error": f"Unknown query_type {query_type!r}."}


def search_knowledge_base(category: str) -> dict:
    """Search the technical knowledge base for a solution.

    Args:
        category: One of:
            - "KB_EXP_DATA": data export errors, CSV/JSON export failures, row limits
            - "KB_API_LIM": API rate limits, throttling, quota questions
            - "KB_AUTH_SSO": login, password reset, SSO / SAML setup

    Returns:
        A dict with `article_id` and `solution`. Falls back to a generic
        "please provide more details" article if category is not recognized.
    """
    if category == "KB_EXP_DATA":
        return {"article_id": "KB-1042", "solution": "Clear browser cache and retry. Free-plan exports are capped at 10k rows."}
    if category == "KB_API_LIM":
        return {"article_id": "KB-0891", "solution": "Default rate limit is 100 req/min. Enterprise gets 1000 req/min."}
    if category == "KB_AUTH_SSO":
        return {"article_id": "KB-0567", "solution": "Reset at /reset-password. For SSO, check Settings > SSO."}
    return {"article_id": "KB-0001", "solution": "Please provide more details."}


def build_agents() -> LlmAgent:
    """Build the multi-agent customer support system."""
    billing_agent = LlmAgent(
        name="billing_agent",
        model=MODEL,
        description="Handles billing questions: balances, charges, refund status.",
        instruction=(
            "You are a billing support specialist. "
            "Use lookup_billing to answer the customer. "
            "Summarize the result with amounts, dates, and the next step."
        ),
        tools=[lookup_billing],
    )
    technical_agent = LlmAgent(
        name="technical_agent",
        model=MODEL,
        description="Handles product bugs, API questions, login/SSO, and troubleshooting.",
        instruction=(
            "You are a technical support specialist. "
            "Use search_knowledge_base for bugs, exports, login, SSO, and API questions. "
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
            "Delegate billing issues to billing_agent; product, login, export, SSO, and API issues to technical_agent. "
            "Do not answer specialist questions yourself - always delegate first, then return a concise final response."
        ),
        sub_agents=[billing_agent, technical_agent],
    )
