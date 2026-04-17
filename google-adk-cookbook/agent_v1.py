"""
Initial (v1) customer support agent.

This version ships with vague tool docstrings and minimal agent instructions.
The underlying billing and KB APIs use opaque internal enum codes
(`BIL_ACCT_01`, `KB_EXP_DATA`, ...) but the tool docstrings do not document
them, so the model has to guess the right enum value from the query. This
is the "before" state we evaluate to measure improvement in `agent_v2.py`.
"""

from google.adk.agents import LlmAgent

MODEL = "gemini-flash-latest"


def lookup_billing(customer_id: str, query_type: str) -> dict:
    """Look up billing info."""
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
    """Search the KB."""
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
        description="Billing.",
        instruction="Help with billing. Use tools if useful.",
        tools=[lookup_billing],
    )
    technical_agent = LlmAgent(
        name="technical_agent",
        model=MODEL,
        description="Tech.",
        instruction="Help with technical issues. Use tools if useful.",
        tools=[search_knowledge_base],
    )
    return LlmAgent(
        name="customer_support",
        model=MODEL,
        description="Customer support.",
        instruction="Answer the customer.",
        sub_agents=[billing_agent, technical_agent],
    )
