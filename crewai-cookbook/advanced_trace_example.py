"""
Advanced example of tracing CrewAI operations with HoneyHive.
This example includes using tools with CrewAI agents and more detailed tracing.
"""

import os
from typing import Dict, Any, List
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process
from crewai.tools import tool
from honeyhive import HoneyHiveTracer, trace

# Load environment variables
load_dotenv()

# Initialize HoneyHive Tracer
HoneyHiveTracer.init(
    api_key=os.getenv("HONEYHIVE_API_KEY"),
    project=os.getenv("HONEYHIVE_PROJECT_NAME", "crewai-advanced-demo"),
    source=os.getenv("HONEYHIVE_SOURCE", "dev"),
    session_name="crewai-market-analysis-crew"
)

# Define custom tools with tracing
@tool
@trace
def search_company_info(query: str) -> str:
    """
    Search for information about a company.
    Args:
        query: The company name or specific query about a company
        
    Returns:
        Information about the company
    """
    # In a real implementation, this would call an API or web search
    # Here we just simulate a response
    return f"Found information about {query}: Company founded in 2010, specializes in AI solutions, has 500 employees, and annual revenue of $50M."

@tool
@trace
def analyze_market_trends(industry: str) -> str:
    """
    Analyze market trends for a specific industry.
    Args:
        industry: The industry to analyze
        
    Returns:
        Market trend analysis for the industry
    """
    # In a real implementation, this would call an API or database
    # Here we just simulate a response
    return f"Market analysis for {industry}: Growing at 12% annually, key players include XYZ Corp and ABC Inc., emerging trends include automation and sustainability."

@tool
@trace
def get_financial_data(ticker: str) -> Dict[str, Any]:
    """
    Get financial data for a company.
    Args:
        ticker: The stock ticker symbol of the company
        
    Returns:
        Financial data for the company
    """
    # In a real implementation, this would call a financial API
    # Here we just simulate a response
    return {
        "ticker": ticker,
        "price": 142.50,
        "market_cap": "1.5T",
        "pe_ratio": 25.3,
        "dividend_yield": 1.2,
        "52_week_high": 180.0,
        "52_week_low": 120.0
    }

@trace
def create_agents() -> Dict[str, Agent]:
    """Create and return a dictionary of agents with specific roles and tools."""
    
    market_analyst = Agent(
        role="Market Research Analyst",
        goal="Conduct thorough market research and competitive analysis",
        backstory="You're a seasoned market analyst with expertise in identifying market trends and competitive landscapes.",
        verbose=True,
        allow_delegation=True,
        tools=[search_company_info, analyze_market_trends]
    )
    
    financial_analyst = Agent(
        role="Financial Analyst",
        goal="Analyze financial data and provide investment recommendations",
        backstory="You're a financial expert with a strong background in financial analysis and investment strategies.",
        verbose=True,
        allow_delegation=True,
        tools=[get_financial_data]
    )
    
    strategic_advisor = Agent(
        role="Strategic Business Advisor",
        goal="Develop strategic recommendations based on market and financial analysis",
        backstory="You're a strategic advisor to C-level executives, known for your ability to synthesize information and develop actionable strategies.",
        verbose=True,
        allow_delegation=False
    )
    
    return {
        "market_analyst": market_analyst,
        "financial_analyst": financial_analyst,
        "strategic_advisor": strategic_advisor
    }

@trace
def create_tasks(agents: Dict[str, Agent], company: str, industry: str) -> List[Task]:
    """Create and return a list of tasks for the agents."""
    
    market_research_task = Task(
        description=f"Research {company} and analyze its position in the {industry} industry. Identify key competitors and market trends.",
        expected_output="A comprehensive market analysis including company positioning, key competitors, and market trends.",
        agent=agents["market_analyst"]
    )
    
    financial_analysis_task = Task(
        description=f"Analyze the financial performance of {company} and its key competitors. Use the get_financial_data tool to gather financial information.",
        expected_output="A detailed financial analysis with key financial metrics and comparison to competitors.",
        agent=agents["financial_analyst"],
        context=[market_research_task]
    )
    
    strategic_recommendations_task = Task(
        description=f"Based on the market and financial analysis, develop strategic recommendations for {company} to improve its market position and financial performance.",
        expected_output="A set of strategic recommendations with clear rationale and expected outcomes.",
        agent=agents["strategic_advisor"],
        context=[market_research_task, financial_analysis_task]
    )
    
    return [market_research_task, financial_analysis_task, strategic_recommendations_task]

@trace
def run_crew(agents: Dict[str, Agent], tasks: List[Task]) -> str:
    """Create and run a crew with the given agents and tasks."""
    
    crew = Crew(
        agents=list(agents.values()),
        tasks=tasks,
        process=Process.sequential,
        verbose=2
    )
    
    return crew.kickoff()

@trace
def main() -> None:
    """Main function to run the advanced CrewAI demonstration with HoneyHive tracing."""
    
    # Define the analysis parameters
    company = "Tesla"
    industry = "Electric Vehicles"
    
    # Log additional information to the trace
    HoneyHiveTracer.get_current_span().set_attribute("company", company)
    HoneyHiveTracer.get_current_span().set_attribute("industry", industry)
    
    # Create agents and tasks
    agents = create_agents()
    tasks = create_tasks(agents, company, industry)
    
    # Run the crew and get the result
    result = run_crew(agents, tasks)
    
    # Add the final result to the trace
    HoneyHiveTracer.get_current_span().set_attribute("result_length", len(result))
    
    # Print the final result
    print("\n=== FINAL STRATEGIC ANALYSIS ===\n")
    print(result)

if __name__ == "__main__":
    main() 