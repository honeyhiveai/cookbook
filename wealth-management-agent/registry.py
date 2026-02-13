"""
Data Models, Enums, and Tools for Wealth Advisory Platform
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Union
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from honeyhive.tracer.custom import trace
from config import SERPAPI_KEY

# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

class TaskType(Enum):
    PORTFOLIO_ANALYSIS = "portfolio_analysis"
    MARKET_RESEARCH = "market_research"
    INVESTMENT_STRATEGY = "investment_strategy"
    COMPLIANCE_CHECK = "compliance_check"
    CLIENT_COMMUNICATION = "client_communication"
    TECHNICAL = "technical"
    GENERAL = "general"

@dataclass
class SubTask:
    id: str
    description: str
    type: TaskType
    complexity: int  # 1-5
    dependencies: List[str] = field(default_factory=list)
    required_tools: List[str] = field(default_factory=list)
    required_capabilities: List[str] = field(default_factory=list)

@dataclass
class TaskDecomposition:
    original_query: str
    subtasks: List[SubTask]
    execution_order: List[str]  # Task IDs in order
    parallel_groups: List[List[str]]  # Groups of task IDs that can run in parallel

@dataclass
class AgentCapability:
    name: str
    description: str
    proficiency: float  # 0.0 to 1.0

@dataclass
class DelegationDecision:
    from_agent: str
    to_agent: str
    task: SubTask
    reason: str
    confidence: float

@dataclass
class ConversationContext:
    conversation_id: str
    turns: List[Dict[str, Any]]
    user_preferences: Dict[str, Any]
    task_outcomes: Dict[str, Any]
    active_agents: List[str]

# ---------------------------------------------------------------------------
# Wealth Advisory Tools with Proper Tracing
# ---------------------------------------------------------------------------

@trace()
def tool_market_data_search(query: str) -> str:
    """Search for market data, research reports, and financial news using SerpAPI."""
    try:
        import requests
        resp = requests.get(
            "https://serpapi.com/search.json",
            params={
                "q": f"{query} financial markets investment",
                "api_key": SERPAPI_KEY,
                "engine": "google",
                "num": 6,
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as err:
        return f"Market data search error: {err}"

    results: List[str] = []
    for res in data.get("organic_results", [])[:6]:
        title = res.get("title", "No title")
        snippet = res.get("snippet", "")
        link = res.get("link", "")
        results.append(f"• {title} – {snippet}\n  {link}")

    return f"Market research results for '{query}':\n" + ("\n".join(results) or "No results found.")

@trace()
def tool_client_portfolio_query(query: str) -> str:
    """Query client portfolio data including holdings, transactions, and account details."""
    # Simulated portfolio database query
    return f"""Client Portfolio Query: {query}

Portfolio Holdings:
- US Large Cap Equities: $450,000 (45%)
- International Developed: $150,000 (15%)
- Fixed Income - Investment Grade: $200,000 (20%)
- Fixed Income - High Yield: $50,000 (5%)
- Alternative Investments: $100,000 (10%)
- Cash & Equivalents: $50,000 (5%)

Total AUM: $1,000,000
Risk Profile: Moderate Growth
Investment Horizon: 10+ years
Last Rebalance: 6 months ago"""

@trace()
def tool_financial_calculator(calculation: str) -> str:
    """Execute financial calculations including projections, Monte Carlo simulations, and scenario analysis."""
    try:
        # Simple eval for demo - DO NOT use in production
        result = eval(calculation) if len(calculation) < 100 and not any(bad in calculation for bad in ['import', 'exec', '__']) else "Calculation disabled for safety"
        return f"Financial calculation result: {result}"
    except Exception as e:
        return f"""Financial Projection for: {calculation}

Monte Carlo Simulation (1000 iterations):
- Expected Return (median): 7.2% annually
- 25th Percentile: 4.1%
- 75th Percentile: 10.8%
- Probability of Meeting Goal: 78%

Projected Portfolio Value (10 years):
- Conservative: $1,480,000
- Expected: $1,970,000
- Optimistic: $2,590,000"""

@trace()
def tool_policy_document_retriever(query: str) -> str:
    """Retrieve investment policy documents, compliance guidelines, and regulatory requirements."""
    # Simulated RAG retrieval for wealth management
    return f"""Policy Documents Retrieved for: {query}

[Doc1: Investment Policy Statement Guidelines]
- Outlines client suitability requirements
- Risk tolerance assessment criteria
- Rebalancing triggers and thresholds

[Doc2: Regulatory Compliance - Fiduciary Standards]
- SEC Regulation Best Interest requirements
- Suitability documentation standards
- Disclosure obligations

[Doc3: Product Due Diligence Framework]
- Approved product list criteria
- Alternative investment guidelines
- Concentration limits by asset class"""

@trace()
def tool_portfolio_analytics(params: str) -> str:
    """Perform portfolio analytics including risk metrics, performance attribution, and optimization analysis."""
    # Simulated portfolio analytics
    return f"""Portfolio Analytics Report: {params}

Risk Metrics:
- Portfolio Beta: 0.92
- Standard Deviation: 12.4%
- Sharpe Ratio: 0.85
- Max Drawdown (3yr): -18.2%
- Value at Risk (95%): -2.1% daily

Performance Attribution (YTD):
- Asset Allocation Effect: +1.2%
- Security Selection Effect: +0.8%
- Interaction Effect: +0.1%
- Total Active Return: +2.1%

Style Analysis:
- Growth Tilt: Moderate
- Quality Factor: High
- Momentum Exposure: Low"""


class MarketDataSearchTool(BaseTool):
    name: str = "market_data_search"
    description: str = "Search for market data, research reports, economic indicators, and financial news."
    
    def _run(self, query: str) -> str:
        return tool_market_data_search(query)

class ClientPortfolioQueryTool(BaseTool):
    name: str = "client_portfolio_query"
    description: str = "Query client portfolio holdings, transactions, account details, and investment history."
    
    def _run(self, query: str) -> str:
        return tool_client_portfolio_query(query)

class FinancialCalculatorTool(BaseTool):
    name: str = "financial_calculator"
    description: str = "Execute financial projections, Monte Carlo simulations, and scenario analysis."
    
    def _run(self, calculation: str) -> str:
        return tool_financial_calculator(calculation)

class PolicyDocumentRetrieverToolSchema(BaseModel):
    """Schema that accepts query as string or dict (LLM sometimes passes param schema as value)."""
    query: Union[str, Dict[str, Any]] = Field(description="Search query for policy documents, compliance guidelines, or regulatory requirements.")


class PolicyDocumentRetrieverTool(BaseTool):
    name: str = "policy_document_retriever"
    description: str = "Retrieve investment policy documents, compliance guidelines, and regulatory requirements."
    args_schema: type[BaseModel] = PolicyDocumentRetrieverToolSchema

    def _run(self, query: Union[str, Dict[str, Any]]) -> str:
        # Normalize: LLM sometimes passes {"description": "...", "type": "str"} instead of a string
        if isinstance(query, dict):
            query = query.get("description") or query.get("query") or str(query)
        return tool_policy_document_retriever(str(query))

class PortfolioAnalyticsTool(BaseTool):
    name: str = "portfolio_analytics"
    description: str = "Perform portfolio risk analysis, performance attribution, and optimization recommendations."
    
    def _run(self, params: str) -> str:
        return tool_portfolio_analytics(params)


# Tool Registry
TOOL_REGISTRY = {
    "market_data_search": MarketDataSearchTool(),
    "client_portfolio_query": ClientPortfolioQueryTool(),
    "financial_calculator": FinancialCalculatorTool(),
    "policy_document_retriever": PolicyDocumentRetrieverTool(),
    "portfolio_analytics": PortfolioAnalyticsTool(),
}