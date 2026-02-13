"""
Client Advisory Task Analysis, Routing, Delegation, and Execution
"""

import json
from typing import Dict, Any, List, Optional, Tuple
import openai
from crewai import Agent
from honeyhive.tracer.custom import trace
from config import OPENAI_MODEL
from registry import (
    TaskDecomposition, SubTask, TaskType, ConversationContext, 
    DelegationDecision
)
from agents import BaseSpecializedAgent, AGENT_REGISTRY

# ---------------------------------------------------------------------------
# Advisory Task Analysis with LLM
# ---------------------------------------------------------------------------

class AdvisoryTaskAnalyzer:
    """Uses LLM to intelligently decompose and analyze client advisory requests."""
    
    def __init__(self):
        self.client = openai.Client()
    
    @trace(config={"model": OPENAI_MODEL})
    def analyze_client_inquiry(self, query: str, context: Optional[ConversationContext] = None) -> TaskDecomposition:
        """Decompose client inquiry into advisory subtasks with dependencies."""
        
        system_prompt = """You are an expert wealth advisory task analyst at a Universal Bank. 
        Analyze client inquiries and decompose them into actionable subtasks for our specialist team.
        
        For each subtask identify:
        1. Task type (portfolio_analysis, market_research, investment_strategy, compliance_check, client_communication, technical, general)
        2. Complexity (1-5)
        3. Dependencies on other tasks
        4. Required tools (market_data_search, client_portfolio_query, portfolio_analytics, financial_calculator, policy_document_retriever)
        5. Required specialist capabilities
        
        Return a JSON with this structure:
        {
            "subtasks": [
                {
                    "id": "task_1",
                    "description": "...",
                    "type": "portfolio_analysis",
                    "complexity": 3,
                    "dependencies": [],
                    "required_tools": ["client_portfolio_query"],
                    "required_capabilities": ["portfolio_optimization", "risk_modeling"]
                }
            ],
            "execution_order": ["task_1", "task_2"],
            "parallel_groups": [["task_1", "task_3"], ["task_2"]]
        }
        
        Consider wealth management context:
        - Portfolio reviews need quantitative analysis before strategic recommendations
        - Investment recommendations require compliance checks
        - Client communications should synthesize findings from other specialists
        """
        
        context_info = ""
        if context:
            context_info = f"\n\nClient conversation history:\n{json.dumps(context.turns[-3:])}"
        
        response = self.client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt + "\n\nIMPORTANT: Return ONLY valid JSON, no other text."},
                {"role": "user", "content": f"Client inquiry: {query}{context_info}"}
            ]
        )
        
        try:
            analysis = json.loads(response.choices[0].message.content)
        except json.JSONDecodeError:
            # Fallback if JSON parsing fails
            print("Warning: Failed to parse JSON, using fallback decomposition")
            analysis = {
                "subtasks": [{
                    "id": "task_1",
                    "description": query,
                    "type": "general",
                    "complexity": 3,
                    "dependencies": [],
                    "required_tools": ["market_data_search"],
                    "required_capabilities": ["market_research"]
                }],
                "execution_order": ["task_1"],
                "parallel_groups": [["task_1"]]
            }
        
        # Convert to dataclass objects
        subtasks = []
        for st in analysis["subtasks"]:
            subtasks.append(SubTask(
                id=st["id"],
                description=st["description"],
                type=TaskType(st["type"]),
                complexity=st["complexity"],
                dependencies=st.get("dependencies", []),
                required_tools=st.get("required_tools", []),
                required_capabilities=st.get("required_capabilities", [])
            ))
        
        return TaskDecomposition(
            original_query=query,
            subtasks=subtasks,
            execution_order=analysis["execution_order"],
            parallel_groups=analysis.get("parallel_groups", [[t.id] for t in subtasks])
        )

# ---------------------------------------------------------------------------
# Intelligent Specialist Router with LLM
# ---------------------------------------------------------------------------

class SpecialistRouter:
    """LLM-powered routing to wealth advisory specialists."""
    
    def __init__(self):
        self.client = openai.Client()
        self.specialist_pool = {name: agent_class() for name, agent_class in AGENT_REGISTRY.items()}
    
    @trace(config={"model": OPENAI_MODEL})
    def select_specialist_for_task(self, task: SubTask, available_specialists: Optional[List[str]] = None) -> Tuple[BaseSpecializedAgent, float]:
        """Select the best wealth advisory specialist for a specific task."""
        
        if available_specialists is None:
            available_specialists = list(self.specialist_pool.keys())
        
        # First, do capability-based scoring
        specialist_scores = {}
        for specialist_name in available_specialists:
            specialist = self.specialist_pool[specialist_name]
            score = specialist.get_capability_score(task.required_capabilities)
            specialist_scores[specialist_name] = score
        
        # Then use LLM for nuanced selection
        specialist_descriptions = "\n".join([
            f"- {name}: {specialist.role} (capability score: {score:.2f})"
            for name, (specialist, score) in [(n, (self.specialist_pool[n], specialist_scores[n])) for n in available_specialists]
        ])
        
        response = self.client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "You are a wealth advisory team coordinator. Match client tasks with the most suitable specialist. Return JSON with 'agent' and 'confidence' (0-1). Return ONLY valid JSON, no other text."},
                {"role": "user", "content": f"Client Task: {task.description}\nType: {task.type.value}\nComplexity: {task.complexity}\nRequired capabilities: {task.required_capabilities}\n\nAvailable specialists:\n{specialist_descriptions}"}
            ]
        )
        
        try:
            decision = json.loads(response.choices[0].message.content)
            selected_specialist_name = decision["agent"]
            confidence = decision["confidence"]
        except (json.JSONDecodeError, KeyError):
            # Fallback to capability-based selection
            print("Warning: Failed to parse specialist selection, using capability scores")
            best_specialist = max(available_specialists, key=lambda name: specialist_scores[name])
            selected_specialist_name = best_specialist
            confidence = specialist_scores[best_specialist]
        
        return self.specialist_pool[selected_specialist_name], confidence
    
    @trace()
    def create_advisory_execution_plan(self, decomposition: TaskDecomposition) -> Dict[str, Any]:
        """Create a detailed execution plan for all advisory subtasks."""
        
        execution_plan = {
            "parallel_groups": decomposition.parallel_groups,
            "task_assignments": {},
            "delegation_paths": []
        }
        
        for task in decomposition.subtasks:
            specialist, confidence = self.select_specialist_for_task(task)
            execution_plan["task_assignments"][task.id] = {
                "agent": specialist.name,
                "confidence": confidence,
                "task": task
            }
        
        return execution_plan

# ---------------------------------------------------------------------------
# Advanced Delegation Manager
# ---------------------------------------------------------------------------

class DelegationManager:
    """Manages specialist delegation patterns for wealth advisory."""
    
    def __init__(self, max_depth: int = 5):
        self.max_depth = max_depth
        self.delegation_history: List[DelegationDecision] = []
        self.client = openai.Client()
    
    @trace(config={"model": OPENAI_MODEL})
    def evaluate_delegation_need(self, specialist: BaseSpecializedAgent, task: SubTask, depth: int) -> Optional[DelegationDecision]:
        """Evaluate if task should be delegated to another specialist."""
        
        if depth >= self.max_depth:
            return None
        
        # Use LLM to decide on delegation
        response = self.client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "Determine if this wealth advisory task should be delegated to another specialist. Return JSON with 'should_delegate' (bool), 'to_agent' (str or null), 'reason' (str), 'confidence' (0-1). Return ONLY valid JSON, no other text."},
                {"role": "user", "content": f"Current specialist: {specialist.name} ({specialist.role})\nTask: {task.description}\nTask complexity: {task.complexity}\nSpecialist capabilities: {list(specialist.capabilities.keys())}\nRequired capabilities: {task.required_capabilities}"}
            ]
        )
        
        try:
            decision_data = json.loads(response.choices[0].message.content)
        except json.JSONDecodeError:
            # Default to no delegation if parsing fails
            print("Warning: Failed to parse delegation decision, proceeding without delegation")
            decision_data = {"should_delegate": False, "to_agent": None, "reason": "JSON parsing failed", "confidence": 0.5}
        
        if decision_data["should_delegate"] and decision_data["to_agent"]:
            decision = DelegationDecision(
                from_agent=specialist.name,
                to_agent=decision_data["to_agent"],
                task=task,
                reason=decision_data["reason"],
                confidence=decision_data["confidence"]
            )
            self.delegation_history.append(decision)
            return decision
        
        return None

# ---------------------------------------------------------------------------
# Specialist Execution Coordinator with Proper Tracing
# ---------------------------------------------------------------------------

class SpecialistExecutor:
    """Handles specialist execution with proper trace hierarchy."""
    
    def __init__(self, delegation_manager: DelegationManager):
        self.delegation_manager = delegation_manager
        self.router = SpecialistRouter()
    
    @trace()
    def coordinate_specialist_execution(self, specialist_name: str, task: SubTask, depth: int = 0) -> Dict[str, Any]:
        """Coordinate the execution of a task by the appropriate specialist."""
        
        # Get the specialist instance
        if specialist_name not in self.router.specialist_pool:
            specialist = AGENT_REGISTRY[specialist_name]()
        else:
            specialist = self.router.specialist_pool[specialist_name]
        
        # Check if delegation is needed
        delegation = self.delegation_manager.evaluate_delegation_need(specialist, task, depth)
        
        if delegation and delegation.to_agent in AGENT_REGISTRY:
            # Delegate to another specialist
            print(f"\n🔄 Delegating from {specialist.name} to {delegation.to_agent}: {delegation.reason}")
            return self.coordinate_specialist_execution(delegation.to_agent, task, depth + 1)
        
        # Execute with current specialist using its specific traced method
        if specialist_name == "market_intelligence_analyst":
            result = specialist.execute_market_intelligence_analyst(task)
        elif specialist_name == "quantitative_analyst":
            result = specialist.execute_quantitative_analyst(task)
        elif specialist_name == "wealth_strategist":
            result = specialist.execute_wealth_strategist(task)
        elif specialist_name == "fintech_solutions_architect":
            result = specialist.execute_fintech_solutions_architect(task)
        elif specialist_name == "client_communications_specialist":
            result = specialist.execute_client_communications_specialist(task)
        elif specialist_name == "regulatory_compliance_officer":
            result = specialist.execute_regulatory_compliance_officer(task)
        else:
            raise ValueError(f"Unknown specialist type: {specialist_name}")
        
        return {
            "agent": specialist.name,
            "task_id": task.id,
            "task_description": task.description,
            "result": result,
            "tools_used": task.required_tools,
            "delegation_depth": depth
        }

# ---------------------------------------------------------------------------
# Client Advisory Orchestrator
# ---------------------------------------------------------------------------

class ClientAdvisoryOrchestrator:
    """Main orchestrator that coordinates the wealth advisory multi-agent workflow."""
    
    def __init__(self):
        self.task_analyzer = AdvisoryTaskAnalyzer()
        self.router = SpecialistRouter()
        self.delegation_manager = DelegationManager()
        self.specialist_executor = SpecialistExecutor(self.delegation_manager)
        self.client = openai.Client()
        
        self.agent = Agent(
            role="Client Advisory Orchestrator",
            goal="Intelligently analyze client inquiries and coordinate the wealth advisory specialist team to provide comprehensive recommendations",
            backstory="You are the lead orchestrator for the wealth advisory platform, with deep understanding of client needs and specialist capabilities.",
            verbose=True,
            allow_delegation=True,
            llm_config={"temperature": 0.1}
        )
    
    @trace()
    def orchestrate_advisory_workflow(self, query: str, context: Optional[ConversationContext] = None) -> Dict[str, Any]:
        """Main orchestration function that coordinates the wealth advisory multi-agent workflow."""
        
        # 1. Analyze and decompose the client inquiry
        print("\n🔍 Analyzing client inquiry...")
        decomposition = self.task_analyzer.analyze_client_inquiry(query, context)
        
        print(f"\n📋 Identified {len(decomposition.subtasks)} advisory tasks:")
        for task in decomposition.subtasks:
            print(f"  - {task.id}: {task.description} (type: {task.type.value}, complexity: {task.complexity})")
        
        # 2. Plan execution strategy
        print("\n🎯 Planning specialist assignments...")
        execution_plan = self.router.create_advisory_execution_plan(decomposition)
        
        # 3. Execute tasks with proper chains
        all_results = self._execute_advisory_plan(execution_plan)
        
        # 4. Synthesize results into client advisory
        final_response = self._synthesize_advisory_response(query, decomposition, all_results)
        
        return {
            "response": final_response,
            "decomposition": decomposition,
            "execution_plan": execution_plan,
            "task_results": all_results,
            "delegation_history": self.delegation_manager.delegation_history
        }
    
    @trace()
    def _execute_advisory_plan(self, execution_plan: Dict[str, Any]) -> Dict[str, Any]:
        """Execute all advisory tasks according to the plan."""
        
        results = {}
        
        for parallel_group in execution_plan["parallel_groups"]:
            print(f"\n⚡ Executing specialist group: {parallel_group}")
            
            for task_id in parallel_group:
                assignment = execution_plan["task_assignments"][task_id]
                task = assignment["task"]
                specialist_name = assignment["agent"]
                
                print(f"\n🤖 Assigning {task_id} to {specialist_name} (confidence: {assignment['confidence']:.2f})")
                
                # Execute with proper specialist chain
                result = self.specialist_executor.coordinate_specialist_execution(specialist_name, task)
                results[task_id] = result
        
        return results
    
    @trace(config={"model": OPENAI_MODEL})
    def _synthesize_advisory_response(self, original_query: str, decomposition: TaskDecomposition, results: Dict[str, Any]) -> str:
        """Synthesize all specialist findings into a cohesive client advisory response."""
        
        synthesis_prompt = f"""As a senior wealth advisor, synthesize these specialist findings into a clear, actionable client advisory response.
        
Original Client Inquiry: {original_query}

Specialist Findings:
"""
        for task_id, result in results.items():
            task_desc = next(t.description for t in decomposition.subtasks if t.id == task_id)
            specialist_used = result["agent"]
            task_result = result["result"]
            synthesis_prompt += f"\n{task_id} ({task_desc})\nSpecialist: {specialist_used}\nFindings:\n{task_result}\n"
        
        synthesis_prompt += """

Please provide a comprehensive advisory response that:
1. Addresses the client's original inquiry directly
2. Integrates insights from all specialist analyses
3. Provides clear, actionable recommendations
4. Highlights any risks or considerations
5. Uses professional wealth advisory language appropriate for client communication
"""
        
        response = self.client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "You are a senior wealth advisor at a Universal Bank. Synthesize specialist findings into clear, professional client advisory communications."},
                {"role": "user", "content": synthesis_prompt}
            ]
        )
        
        return response.choices[0].message.content


# Backward compatibility alias
PrincipalRouterAgent = ClientAdvisoryOrchestrator
