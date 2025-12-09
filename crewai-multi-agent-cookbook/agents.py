"""
All Agent Classes and Registry
"""

from typing import List
from crewai import Agent, Task, Crew, Process
from honeyhive.tracer import trace
from registry import SubTask, AgentCapability, TOOL_REGISTRY

# ---------------------------------------------------------------------------
# Dynamic Agent Pool
# ---------------------------------------------------------------------------

class BaseSpecializedAgent:
    """Base class for specialized agents."""
    
    def __init__(self, name: str, role: str, capabilities: List[AgentCapability], tools: List[str]):
        self.name = name
        self.role = role
        self.capabilities = {cap.name: cap for cap in capabilities}
        self.tools = [TOOL_REGISTRY[t] for t in tools if t in TOOL_REGISTRY]
        
        self.agent = Agent(
            role=role,
            goal=f"Complete tasks that require {', '.join(self.capabilities.keys())}",
            backstory=f"Expert {role} with deep knowledge and proven track record.",
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

# Specialized Agent Implementations
class ResearchSpecialistAgent(BaseSpecializedAgent):
    def __init__(self):
        super().__init__(
            name="research_specialist",
            role="Senior Research Analyst",
            capabilities=[
                AgentCapability("web_research", "Expert at finding and synthesizing web information", 0.95),
                AgentCapability("fact_checking", "Validates information accuracy", 0.9),
                AgentCapability("source_evaluation", "Assesses source credibility", 0.85),
                AgentCapability("trend_analysis", "Identifies patterns and trends", 0.8),
            ],
            tools=["search_web", "document_retriever"]
        )
    
    @trace()
    def execute_research_specialist(self, task: SubTask) -> str:
        """Execute research specialist agent tasks."""
        return self._run_crew_task(task)
    
    def _run_crew_task(self, task: SubTask) -> str:
        """Internal method to run CrewAI task."""
        crew_task = Task(
            description=task.description,
            agent=self.agent,
            tools=self.tools,
            expected_output=f"Complete analysis/answer for: {task.description}"
        )
        
        crew = Crew(
            agents=[self.agent],
            tasks=[crew_task],
            process=Process.sequential,
            verbose=True
        )
        
        return crew.kickoff()

class DataAnalystAgent(BaseSpecializedAgent):
    def __init__(self):
        super().__init__(
            name="data_analyst",
            role="Senior Data Analyst",
            capabilities=[
                AgentCapability("statistical_analysis", "Advanced statistical methods", 0.9),
                AgentCapability("data_visualization", "Creates insightful visualizations", 0.85),
                AgentCapability("predictive_modeling", "Builds predictive models", 0.8),
                AgentCapability("database_operations", "Expert at data querying", 0.95),
            ],
            tools=["database_query", "code_executor"]
        )
    
    @trace()
    def execute_data_analyst(self, task: SubTask) -> str:
        """Execute data analyst agent tasks."""
        return self._run_crew_task(task)
    
    def _run_crew_task(self, task: SubTask) -> str:
        """Internal method to run CrewAI task."""
        crew_task = Task(
            description=task.description,
            agent=self.agent,
            tools=self.tools,
            expected_output=f"Complete analysis/answer for: {task.description}"
        )
        
        crew = Crew(
            agents=[self.agent],
            tasks=[crew_task],
            process=Process.sequential,
            verbose=True
        )
        
        return crew.kickoff()

class FinancialAdvisorAgent(BaseSpecializedAgent):
    def __init__(self):
        super().__init__(
            name="financial_advisor",
            role="Senior Financial Advisor",
            capabilities=[
                AgentCapability("investment_analysis", "Portfolio and investment expertise", 0.9),
                AgentCapability("risk_assessment", "Evaluates financial risks", 0.95),
                AgentCapability("tax_planning", "Tax optimization strategies", 0.8),
                AgentCapability("market_analysis", "Market trends and forecasting", 0.85),
            ],
            tools=["financial_analysis", "search_web", "code_executor"]
        )
    
    @trace()
    def execute_financial_advisor(self, task: SubTask) -> str:
        """Execute financial advisor agent tasks."""
        return self._run_crew_task(task)
    
    def _run_crew_task(self, task: SubTask) -> str:
        """Internal method to run CrewAI task."""
        crew_task = Task(
            description=task.description,
            agent=self.agent,
            tools=self.tools,
            expected_output=f"Complete analysis/answer for: {task.description}"
        )
        
        crew = Crew(
            agents=[self.agent],
            tasks=[crew_task],
            process=Process.sequential,
            verbose=True
        )
        
        return crew.kickoff()

class TechnicalExpertAgent(BaseSpecializedAgent):
    def __init__(self):
        super().__init__(
            name="technical_expert",
            role="Senior Technical Architect",
            capabilities=[
                AgentCapability("system_design", "Designs complex systems", 0.9),
                AgentCapability("code_review", "Reviews and improves code", 0.85),
                AgentCapability("debugging", "Identifies and fixes issues", 0.9),
                AgentCapability("performance_optimization", "Optimizes system performance", 0.8),
            ],
            tools=["code_executor", "document_retriever"]
        )
    
    @trace()
    def execute_technical_expert(self, task: SubTask) -> str:
        """Execute technical expert agent tasks."""
        return self._run_crew_task(task)
    
    def _run_crew_task(self, task: SubTask) -> str:
        """Internal method to run CrewAI task."""
        crew_task = Task(
            description=task.description,
            agent=self.agent,
            tools=self.tools,
            expected_output=f"Complete analysis/answer for: {task.description}"
        )
        
        crew = Crew(
            agents=[self.agent],
            tasks=[crew_task],
            process=Process.sequential,
            verbose=True
        )
        
        return crew.kickoff()

class CreativeWriterAgent(BaseSpecializedAgent):
    def __init__(self):
        super().__init__(
            name="creative_writer",
            role="Senior Content Strategist",
            capabilities=[
                AgentCapability("content_creation", "Creates engaging content", 0.95),
                AgentCapability("storytelling", "Crafts compelling narratives", 0.9),
                AgentCapability("editing", "Refines and polishes content", 0.85),
                AgentCapability("audience_analysis", "Understands target audiences", 0.8),
            ],
            tools=["search_web", "document_retriever"]
        )
    
    @trace()
    def execute_creative_writer(self, task: SubTask) -> str:
        """Execute creative writer agent tasks."""
        return self._run_crew_task(task)
    
    def _run_crew_task(self, task: SubTask) -> str:
        """Internal method to run CrewAI task."""
        crew_task = Task(
            description=task.description,
            agent=self.agent,
            tools=self.tools,
            expected_output=f"Complete analysis/answer for: {task.description}"
        )
        
        crew = Crew(
            agents=[self.agent],
            tasks=[crew_task],
            process=Process.sequential,
            verbose=True
        )
        
        return crew.kickoff()

class LegalAdvisorAgent(BaseSpecializedAgent):
    def __init__(self):
        super().__init__(
            name="legal_advisor",
            role="Senior Legal Counsel",
            capabilities=[
                AgentCapability("contract_review", "Analyzes legal documents", 0.9),
                AgentCapability("compliance_check", "Ensures regulatory compliance", 0.95),
                AgentCapability("risk_mitigation", "Identifies legal risks", 0.85),
                AgentCapability("legal_research", "Researches case law and regulations", 0.9),
            ],
            tools=["document_retriever", "search_web"]
        )
    
    @trace()
    def execute_legal_advisor(self, task: SubTask) -> str:
        """Execute legal advisor agent tasks."""
        return self._run_crew_task(task)
    
    def _run_crew_task(self, task: SubTask) -> str:
        """Internal method to run CrewAI task."""
        crew_task = Task(
            description=task.description,
            agent=self.agent,
            tools=self.tools,
            expected_output=f"Complete analysis/answer for: {task.description}"
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
    "research_specialist": ResearchSpecialistAgent,
    "data_analyst": DataAnalystAgent,
    "financial_advisor": FinancialAdvisorAgent,
    "technical_expert": TechnicalExpertAgent,
    "creative_writer": CreativeWriterAgent,
    "legal_advisor": LegalAdvisorAgent,
}