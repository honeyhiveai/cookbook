"""
Data Models, Enums, and Tools
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any
from crewai.tools import BaseTool
from honeyhive.tracer import trace
from config import SERPAPI_KEY

# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

class TaskType(Enum):
    RESEARCH = "research"
    ANALYSIS = "analysis"
    CREATIVE = "creative"
    TECHNICAL = "technical"
    FINANCIAL = "financial"
    LEGAL = "legal"
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
# Enhanced Tools with Proper Tracing
# ---------------------------------------------------------------------------

@trace()
def tool_search_web(query: str) -> str:
    """SerpAPI Google search with proper tracing."""
    try:
        import requests
        resp = requests.get(
            "https://serpapi.com/search.json",
            params={
                "q": query,
                "api_key": SERPAPI_KEY,
                "engine": "google",
                "num": 6,
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as err:
        return f"SerpAPI error: {err}"

    results: List[str] = []
    for res in data.get("organic_results", [])[:6]:
        title = res.get("title", "No title")
        snippet = res.get("snippet", "")
        link = res.get("link", "")
        results.append(f"• {title} – {snippet}\n  {link}")

    return f"Search results for '{query}':\n" + ("\n".join(results) or "No results found.")

@trace()
def tool_database_query(query: str) -> str:
    """Execute database query with proper tracing."""
    # Simulated database query
    return f"Database results for query: {query}\n[Simulated data: Customer segments, transaction patterns, risk scores]"

@trace()
def tool_code_executor(code: str) -> str:
    """Execute code with proper tracing."""
    try:
        # Simple eval for demo - DO NOT use in production
        result = eval(code) if len(code) < 100 and not any(bad in code for bad in ['import', 'exec', '__']) else "Code execution disabled for safety"
        return f"Code result: {result}"
    except Exception as e:
        return f"Code error: {e}"

@trace()
def tool_document_retriever(query: str) -> str:
    """Retrieve documents with proper tracing."""
    # Simulated RAG retrieval
    return f"Retrieved documents for: {query}\n[Doc1: Policy guidelines]\n[Doc2: Best practices]\n[Doc3: Case studies]"

@trace()
def tool_financial_analysis(params: str) -> str:
    """Perform financial analysis with proper tracing."""
    # Simulated financial analysis
    return f"Financial analysis: {params}\nRisk Score: 0.3\nROI Projection: 12.5%\nMarket Volatility: Medium"

class SearchWebTool(BaseTool):
    name: str = "search_web"
    description: str = "Search the web for up-to-date information using SerpAPI."
    
    def _run(self, query: str) -> str:
        return tool_search_web(query)

class DatabaseQueryTool(BaseTool):
    name: str = "database_query"
    description: str = "Query structured databases for data analysis."
    
    def _run(self, query: str) -> str:
        return tool_database_query(query)

class CodeExecutorTool(BaseTool):
    name: str = "code_executor"
    description: str = "Execute Python code for calculations and data processing."
    
    def _run(self, code: str) -> str:
        return tool_code_executor(code)

class DocumentRetrieverTool(BaseTool):
    name: str = "document_retriever"
    description: str = "Retrieve and analyze documents from knowledge base."
    
    def _run(self, query: str) -> str:
        return tool_document_retriever(query)

class FinancialAnalysisTool(BaseTool):
    name: str = "financial_analysis"
    description: str = "Perform financial calculations and risk assessments."
    
    def _run(self, params: str) -> str:
        return tool_financial_analysis(params)

# Tool Registry
TOOL_REGISTRY = {
    "search_web": SearchWebTool(),
    "database_query": DatabaseQueryTool(),
    "code_executor": CodeExecutorTool(),
    "document_retriever": DocumentRetrieverTool(),
    "financial_analysis": FinancialAnalysisTool(),
}