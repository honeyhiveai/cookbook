"""
Task Analysis, Routing, Delegation, and Execution
"""

import json
from typing import Dict, Any, List, Optional, Tuple
import openai
from crewai import Agent
from honeyhive.tracer import trace
from registry import (
    TaskDecomposition, SubTask, TaskType, ConversationContext, 
    DelegationDecision
)
from agents import BaseSpecializedAgent, AGENT_REGISTRY

# ---------------------------------------------------------------------------
# Task Analysis with LLM
# ---------------------------------------------------------------------------

class TaskAnalyzer:
    """Uses LLM to intelligently decompose and analyze tasks."""
    
    def __init__(self):
        self.client = openai.Client()
    
    @trace()
    def decompose_user_query(self, query: str, context: Optional[ConversationContext] = None) -> TaskDecomposition:
        """Decompose user query into subtasks with dependencies."""
        
        system_prompt = """You are an expert task analyst. Decompose the user query into subtasks.
        For each subtask identify:
        1. Task type (research, analysis, creative, technical, financial, legal, general)
        2. Complexity (1-5)
        3. Dependencies on other tasks
        4. Required tools
        5. Required agent capabilities
        
        Return a JSON with this structure:
        {
            "subtasks": [
                {
                    "id": "task_1",
                    "description": "...",
                    "type": "research",
                    "complexity": 3,
                    "dependencies": [],
                    "required_tools": ["search_web"],
                    "required_capabilities": ["web_research", "fact_checking"]
                }
            ],
            "execution_order": ["task_1", "task_2"],
            "parallel_groups": [["task_1", "task_3"], ["task_2"]]
        }
        """
        
        context_info = ""
        if context:
            context_info = f"\n\nConversation context:\n{json.dumps(context.turns[-3:])}"
        
        response = self.client.chat.completions.create(
            model="gpt-5-mini",
            messages=[
                {"role": "system", "content": system_prompt + "\n\nIMPORTANT: Return ONLY valid JSON, no other text."},
                {"role": "user", "content": f"Query: {query}{context_info}"}
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
                    "required_tools": ["search_web"],
                    "required_capabilities": ["web_research"]
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
# Intelligent Router with LLM
# ---------------------------------------------------------------------------

class IntelligentRouter:
    """LLM-powered routing decisions."""
    
    def __init__(self):
        self.client = openai.Client()
        self.agent_pool = {name: agent_class() for name, agent_class in AGENT_REGISTRY.items()}
    
    @trace()
    def select_agent_for_task(self, task: SubTask, available_agents: Optional[List[str]] = None) -> Tuple[BaseSpecializedAgent, float]:
        """Select the best agent for a specific task using LLM and capability matching."""
        
        if available_agents is None:
            available_agents = list(self.agent_pool.keys())
        
        # First, do capability-based scoring
        agent_scores = {}
        for agent_name in available_agents:
            agent = self.agent_pool[agent_name]
            score = agent.get_capability_score(task.required_capabilities)
            agent_scores[agent_name] = score
        
        # Then use LLM for nuanced selection
        agent_descriptions = "\n".join([
            f"- {name}: {agent.role} (capability score: {score:.2f})"
            for name, (agent, score) in [(n, (self.agent_pool[n], agent_scores[n])) for n in available_agents]
        ])
        
        response = self.client.chat.completions.create(
            model="gpt-5-mini",
            messages=[
                {"role": "system", "content": "You are an expert at matching tasks with agents. Return JSON with 'agent' and 'confidence' (0-1). Return ONLY valid JSON, no other text."},
                {"role": "user", "content": f"Task: {task.description}\nType: {task.type.value}\nComplexity: {task.complexity}\nRequired capabilities: {task.required_capabilities}\n\nAvailable agents:\n{agent_descriptions}"}
            ]
        )
        
        try:
            decision = json.loads(response.choices[0].message.content)
            selected_agent_name = decision["agent"]
            confidence = decision["confidence"]
        except (json.JSONDecodeError, KeyError):
            # Fallback to capability-based selection
            print("Warning: Failed to parse agent selection, using capability scores")
            best_agent = max(available_agents, key=lambda name: agent_scores[name])
            selected_agent_name = best_agent
            confidence = agent_scores[best_agent]
        
        return self.agent_pool[selected_agent_name], confidence
    
    @trace()
    def create_execution_plan(self, decomposition: TaskDecomposition) -> Dict[str, Any]:
        """Create a detailed execution plan for all subtasks."""
        
        execution_plan = {
            "parallel_groups": decomposition.parallel_groups,
            "task_assignments": {},
            "delegation_paths": []
        }
        
        for task in decomposition.subtasks:
            agent, confidence = self.select_agent_for_task(task)
            execution_plan["task_assignments"][task.id] = {
                "agent": agent.name,
                "confidence": confidence,
                "task": task
            }
        
        return execution_plan

# ---------------------------------------------------------------------------
# Advanced Delegation Manager
# ---------------------------------------------------------------------------

class DelegationManager:
    """Manages complex delegation patterns."""
    
    def __init__(self, max_depth: int = 5):
        self.max_depth = max_depth
        self.delegation_history: List[DelegationDecision] = []
        self.client = openai.Client()
    
    @trace()
    def evaluate_delegation_need(self, agent: BaseSpecializedAgent, task: SubTask, depth: int) -> Optional[DelegationDecision]:
        """Evaluate if task should be delegated to another agent."""
        
        if depth >= self.max_depth:
            return None
        
        # Use LLM to decide on delegation
        response = self.client.chat.completions.create(
            model="gpt-5-mini",
            messages=[
                {"role": "system", "content": "Determine if this task should be delegated. Return JSON with 'should_delegate' (bool), 'to_agent' (str or null), 'reason' (str), 'confidence' (0-1). Return ONLY valid JSON, no other text."},
                {"role": "user", "content": f"Current agent: {agent.name} ({agent.role})\nTask: {task.description}\nTask complexity: {task.complexity}\nAgent capabilities: {list(agent.capabilities.keys())}\nRequired capabilities: {task.required_capabilities}"}
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
                from_agent=agent.name,
                to_agent=decision_data["to_agent"],
                task=task,
                reason=decision_data["reason"],
                confidence=decision_data["confidence"]
            )
            self.delegation_history.append(decision)
            return decision
        
        return None

# ---------------------------------------------------------------------------
# Agent Execution Chains with Proper Tracing
# ---------------------------------------------------------------------------

class AgentExecutor:
    """Handles agent execution with proper trace hierarchy."""
    
    def __init__(self, delegation_manager: DelegationManager):
        self.delegation_manager = delegation_manager
        self.router = IntelligentRouter()
    
    @trace()
    def coordinate_agent_execution(self, agent_name: str, task: SubTask, depth: int = 0) -> Dict[str, Any]:
        """Coordinate the execution of a task by the appropriate agent."""
        
        # Get the agent instance
        if agent_name not in self.router.agent_pool:
            agent = AGENT_REGISTRY[agent_name]()
        else:
            agent = self.router.agent_pool[agent_name]
        
        # Check if delegation is needed
        delegation = self.delegation_manager.evaluate_delegation_need(agent, task, depth)
        
        if delegation and delegation.to_agent in AGENT_REGISTRY:
            # Delegate to another agent
            print(f"\n🔄 Delegating from {agent.name} to {delegation.to_agent}: {delegation.reason}")
            return self.coordinate_agent_execution(delegation.to_agent, task, depth + 1)
        
        # Execute with current agent using its specific traced method
        # Call the agent-specific execution method
        if agent_name == "research_specialist":
            result = agent.execute_research_specialist(task)
        elif agent_name == "data_analyst":
            result = agent.execute_data_analyst(task)
        elif agent_name == "financial_advisor":
            result = agent.execute_financial_advisor(task)
        elif agent_name == "technical_expert":
            result = agent.execute_technical_expert(task)
        elif agent_name == "creative_writer":
            result = agent.execute_creative_writer(task)
        elif agent_name == "legal_advisor":
            result = agent.execute_legal_advisor(task)
        else:
            raise ValueError(f"Unknown agent type: {agent_name}")
        
        return {
            "agent": agent.name,
            "task_id": task.id,
            "task_description": task.description,
            "result": result,
            "tools_used": task.required_tools,
            "delegation_depth": depth
        }

# ---------------------------------------------------------------------------
# Principal Router Agent with LLM
# ---------------------------------------------------------------------------

class PrincipalRouterAgent:
    """Enhanced router agent that uses LLM for all decisions."""
    
    def __init__(self):
        self.task_analyzer = TaskAnalyzer()
        self.router = IntelligentRouter()
        self.delegation_manager = DelegationManager()
        self.agent_executor = AgentExecutor(self.delegation_manager)
        self.client = openai.Client()
        
        self.agent = Agent(
            role="Principal Router Agent",
            goal="Intelligently analyze, decompose, and route tasks to the most suitable specialized agents",
            backstory="You are the chief orchestrator with deep understanding of task complexity and agent capabilities.",
            verbose=True,
            allow_delegation=True,
            llm_config={"temperature": 0.1}
        )
    
    @trace()
    def orchestrate_multi_agent_workflow(self, query: str, context: Optional[ConversationContext] = None) -> Dict[str, Any]:
        """Main orchestration function that coordinates the entire multi-agent workflow."""
        
        # 1. Analyze and decompose the query
        print("\n🔍 Analyzing query with LLM...")
        decomposition = self.task_analyzer.decompose_user_query(query, context)
        
        print(f"\n📋 Identified {len(decomposition.subtasks)} subtasks:")
        for task in decomposition.subtasks:
            print(f"  - {task.id}: {task.description} (type: {task.type.value}, complexity: {task.complexity})")
        
        # 2. Plan execution strategy
        print("\n🎯 Planning execution strategy...")
        execution_plan = self.router.create_execution_plan(decomposition)
        
        # 3. Execute tasks with proper chains
        all_results = self._execute_task_plan(execution_plan)
        
        # 4. Synthesize results
        final_response = self._synthesize_results(query, decomposition, all_results)
        
        return {
            "response": final_response,
            "decomposition": decomposition,
            "execution_plan": execution_plan,
            "task_results": all_results,
            "delegation_history": self.delegation_manager.delegation_history
        }
    
    @trace()
    def _execute_task_plan(self, execution_plan: Dict[str, Any]) -> Dict[str, Any]:
        """Execute all tasks according to the plan with proper agent chains."""
        
        results = {}
        
        for parallel_group in execution_plan["parallel_groups"]:
            print(f"\n⚡ Executing parallel group: {parallel_group}")
            
            for task_id in parallel_group:
                assignment = execution_plan["task_assignments"][task_id]
                task = assignment["task"]
                agent_name = assignment["agent"]
                
                print(f"\n🤖 Assigning {task_id} to {agent_name} (confidence: {assignment['confidence']:.2f})")
                
                # Execute with proper agent chain
                result = self.agent_executor.coordinate_agent_execution(agent_name, task)
                results[task_id] = result
        
        return results
    
    @trace()
    def _synthesize_results(self, original_query: str, decomposition: TaskDecomposition, results: Dict[str, Any]) -> str:
        """Synthesize all task results into a cohesive response."""
        
        synthesis_prompt = f"""Synthesize these task results into a cohesive response:
        
Original query: {original_query}

Task results:
"""
        for task_id, result in results.items():
            task_desc = next(t.description for t in decomposition.subtasks if t.id == task_id)
            agent_used = result["agent"]
            task_result = result["result"]
            synthesis_prompt += f"\n{task_id} ({task_desc}) - Agent: {agent_used}:\n{task_result}\n"
        
        response = self.client.chat.completions.create(
            model="gpt-5-mini",
            messages=[
                {"role": "system", "content": "You are a master synthesizer. Combine the task results into a clear, comprehensive response."},
                {"role": "user", "content": synthesis_prompt}
            ]
        )
        
        return response.choices[0].message.content