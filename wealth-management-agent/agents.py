"""
Wealth Advisory Specialist Agents
"""

from typing import List
from crewai import Agent, Task, Crew, Process
from honeyhive.tracer.custom import trace
from registry import SubTask, AgentCapability, TOOL_REGISTRY

# ---------------------------------------------------------------------------
# Dynamic Agent Pool for Wealth Advisory
# ---------------------------------------------------------------------------

class BaseSpecializedAgent:
    """Base class for specialized wealth advisory agents."""
    
    def __init__(self, name: str, role: str, capabilities: List[AgentCapability], tools: List[str]):
        self.name = name
        self.role = role
        self.capabilities = {cap.name: cap for cap in capabilities}
        self.tools = [TOOL_REGISTRY[t] for t in tools if t in TOOL_REGISTRY]
        
        self.agent = Agent(
            role=role,
            goal=f"Provide expert wealth advisory support for {', '.join(self.capabilities.keys())}",
            backstory=f"Senior {role} with extensive experience in wealth management and client advisory services.",
            tools=self.tools,
            verbose=True,
            allow_delegation=True,
            max_iter=5,
        )
    
    def get_capability_score(self, required_capabilities: List[str]) -> float:
        """Calculate how well this agent matches required capabilities."""
        if not required_capabilities:
            return 0.5
        
        total_score = 0
        for req_cap in required_capabilities:
            if req_cap in self.capabilities:
                total_score += self.capabilities[req_cap].proficiency
        
        return total_score / len(required_capabilities)


# Specialized Agent Implementations for Wealth Advisory

class MarketIntelligenceAnalystAgent(BaseSpecializedAgent):
    """Specializes in market research, economic analysis, and investment trends."""
    
    def __init__(self):
        super().__init__(
            name="market_intelligence_analyst",
            role="Senior Market Intelligence Analyst",
            capabilities=[
                AgentCapability("market_research", "Expert at analyzing market trends and investment opportunities", 0.95),
                AgentCapability("economic_analysis", "Interprets macroeconomic indicators and their portfolio impact", 0.9),
                AgentCapability("sector_analysis", "Deep expertise in sector rotation and industry dynamics", 0.85),
                AgentCapability("competitor_intelligence", "Monitors competitor offerings and market positioning", 0.8),
            ],
            tools=["market_data_search", "policy_document_retriever"]
        )
    
    @trace()
    def execute_market_intelligence_analyst(self, task: SubTask) -> str:
        """Execute market intelligence analysis tasks."""
        return self._run_crew_task(task)
    
    def _run_crew_task(self, task: SubTask) -> str:
        """Internal method to run CrewAI task."""
        crew_task = Task(
            description=task.description,
            agent=self.agent,
            tools=self.tools,
            expected_output=f"Comprehensive market intelligence report for: {task.description}"
        )
        
        crew = Crew(
            agents=[self.agent],
            tasks=[crew_task],
            process=Process.sequential,
            verbose=True
        )
        
        return crew.kickoff()


class QuantitativeAnalystAgent(BaseSpecializedAgent):
    """Specializes in portfolio analytics, risk modeling, and quantitative analysis."""
    
    def __init__(self):
        super().__init__(
            name="quantitative_analyst",
            role="Senior Quantitative Analyst",
            capabilities=[
                AgentCapability("portfolio_optimization", "Expert in modern portfolio theory and optimization", 0.95),
                AgentCapability("risk_modeling", "Advanced risk metrics and VaR calculations", 0.9),
                AgentCapability("performance_attribution", "Decomposes portfolio returns by factor and allocation", 0.9),
                AgentCapability("stress_testing", "Scenario analysis and stress testing methodologies", 0.85),
            ],
            tools=["client_portfolio_query", "portfolio_analytics", "financial_calculator"]
        )
    
    @trace()
    def execute_quantitative_analyst(self, task: SubTask) -> str:
        """Execute quantitative analysis tasks."""
        return self._run_crew_task(task)
    
    def _run_crew_task(self, task: SubTask) -> str:
        """Internal method to run CrewAI task."""
        crew_task = Task(
            description=task.description,
            agent=self.agent,
            tools=self.tools,
            expected_output=f"Quantitative analysis with risk metrics for: {task.description}"
        )
        
        crew = Crew(
            agents=[self.agent],
            tasks=[crew_task],
            process=Process.sequential,
            verbose=True
        )
        
        return crew.kickoff()


class WealthStrategistAgent(BaseSpecializedAgent):
    """Specializes in investment strategy, asset allocation, and financial planning."""
    
    def __init__(self):
        super().__init__(
            name="wealth_strategist",
            role="Senior Wealth Strategist",
            capabilities=[
                AgentCapability("asset_allocation", "Strategic and tactical asset allocation expertise", 0.95),
                AgentCapability("retirement_planning", "Comprehensive retirement income planning", 0.9),
                AgentCapability("tax_optimization", "Tax-efficient investment strategies", 0.85),
                AgentCapability("estate_planning", "Wealth transfer and legacy planning considerations", 0.8),
            ],
            tools=["portfolio_analytics", "market_data_search", "financial_calculator"]
        )
    
    @trace()
    def execute_wealth_strategist(self, task: SubTask) -> str:
        """Execute wealth strategy tasks."""
        return self._run_crew_task(task)
    
    def _run_crew_task(self, task: SubTask) -> str:
        """Internal method to run CrewAI task."""
        crew_task = Task(
            description=task.description,
            agent=self.agent,
            tools=self.tools,
            expected_output=f"Strategic wealth advisory recommendation for: {task.description}"
        )
        
        crew = Crew(
            agents=[self.agent],
            tasks=[crew_task],
            process=Process.sequential,
            verbose=True
        )
        
        return crew.kickoff()


class FintechSolutionsArchitectAgent(BaseSpecializedAgent):
    """Specializes in digital banking solutions and platform capabilities."""
    
    def __init__(self):
        super().__init__(
            name="fintech_solutions_architect",
            role="Senior FinTech Solutions Architect",
            capabilities=[
                AgentCapability("digital_onboarding", "Digital client onboarding and KYC automation", 0.9),
                AgentCapability("api_integration", "Wealth platform API integrations and data flows", 0.9),
                AgentCapability("platform_capabilities", "Advisory platform features and capabilities", 0.85),
                AgentCapability("automation_design", "Workflow automation and operational efficiency", 0.85),
            ],
            tools=["financial_calculator", "policy_document_retriever"]
        )
    
    @trace()
    def execute_fintech_solutions_architect(self, task: SubTask) -> str:
        """Execute fintech solutions tasks."""
        return self._run_crew_task(task)
    
    def _run_crew_task(self, task: SubTask) -> str:
        """Internal method to run CrewAI task."""
        crew_task = Task(
            description=task.description,
            agent=self.agent,
            tools=self.tools,
            expected_output=f"Technical solution design for: {task.description}"
        )
        
        crew = Crew(
            agents=[self.agent],
            tasks=[crew_task],
            process=Process.sequential,
            verbose=True
        )
        
        return crew.kickoff()


class ClientCommunicationsSpecialistAgent(BaseSpecializedAgent):
    """Specializes in client communications, reports, and personalized content."""
    
    def __init__(self):
        super().__init__(
            name="client_communications_specialist",
            role="Senior Client Communications Specialist",
            capabilities=[
                AgentCapability("proposal_writing", "Creates compelling investment proposals", 0.95),
                AgentCapability("client_reporting", "Quarterly reviews and performance reports", 0.9),
                AgentCapability("personalized_content", "Tailored client communications and updates", 0.9),
                AgentCapability("presentation_design", "Client meeting materials and presentations", 0.85),
            ],
            tools=["market_data_search", "policy_document_retriever"]
        )
    
    @trace()
    def execute_client_communications_specialist(self, task: SubTask) -> str:
        """Execute client communications tasks."""
        return self._run_crew_task(task)
    
    def _run_crew_task(self, task: SubTask) -> str:
        """Internal method to run CrewAI task."""
        crew_task = Task(
            description=task.description,
            agent=self.agent,
            tools=self.tools,
            expected_output=f"Professional client communication for: {task.description}"
        )
        
        crew = Crew(
            agents=[self.agent],
            tasks=[crew_task],
            process=Process.sequential,
            verbose=True
        )
        
        return crew.kickoff()


class RegulatoryComplianceOfficerAgent(BaseSpecializedAgent):
    """Specializes in regulatory compliance, suitability, and fiduciary requirements."""
    
    def __init__(self):
        super().__init__(
            name="regulatory_compliance_officer",
            role="Senior Regulatory Compliance Officer",
            capabilities=[
                AgentCapability("suitability_review", "Investment suitability and best interest standards", 0.95),
                AgentCapability("kyc_verification", "Know Your Customer and AML compliance", 0.9),
                AgentCapability("regulatory_research", "SEC, FINRA, and state regulatory requirements", 0.9),
                AgentCapability("fiduciary_compliance", "Fiduciary duty and disclosure obligations", 0.85),
            ],
            tools=["policy_document_retriever", "market_data_search"]
        )
    
    @trace()
    def execute_regulatory_compliance_officer(self, task: SubTask) -> str:
        """Execute regulatory compliance tasks."""
        return self._run_crew_task(task)
    
    def _run_crew_task(self, task: SubTask) -> str:
        """Internal method to run CrewAI task."""
        crew_task = Task(
            description=task.description,
            agent=self.agent,
            tools=self.tools,
            expected_output=f"Compliance assessment and recommendations for: {task.description}"
        )
        
        crew = Crew(
            agents=[self.agent],
            tasks=[crew_task],
            process=Process.sequential,
            verbose=True
        )
        
        return crew.kickoff()


# Dynamic Agent Registry
AGENT_REGISTRY = {
    "market_intelligence_analyst": MarketIntelligenceAnalystAgent,
    "quantitative_analyst": QuantitativeAnalystAgent,
    "wealth_strategist": WealthStrategistAgent,
    "fintech_solutions_architect": FintechSolutionsArchitectAgent,
    "client_communications_specialist": ClientCommunicationsSpecialistAgent,
    "regulatory_compliance_officer": RegulatoryComplianceOfficerAgent,
}
