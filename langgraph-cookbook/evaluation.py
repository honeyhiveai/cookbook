"""
CommBank Enhanced Multi-Agent Demo with Sophisticated Orchestration
===================================================================
This enhanced version implements:
1. LLM-powered task decomposition and routing
2. Dynamic agent pool with specializations
3. Intelligent routing based on capabilities
4. Advanced nested delegation patterns
5. Multi-turn conversation support
6. Enhanced tool integration

All powered by CrewAI with HoneyHive tracing.

USAGE:
------
Evaluation Mode (HoneyHive):
   python crewai_multiagent_eval.py evaluate
   
   The evaluation will run with 5 pre-defined example queries that test:
   - Financial analysis capabilities
   - Legal and regulatory research
   - Technical architecture design
   - Creative content generation
   - Tax and investment advice
   
Note: Interactive CLI mode has been removed. All inputs come from the evaluation dataset.
"""

from datetime import datetime
from typing import Dict, Any, Optional
from honeyhive.tracer import HoneyHiveTracer
from honeyhive.tracer.custom import trace
from honeyhive import evaluate

# Import all components from our refactored modules
from config import HONEYHIVE_CONFIG
from registry import ConversationContext
from main import ConversationManager, process_single_query

# ---------------------------------------------------------------------------
# HoneyHive Evaluation Functions
# ---------------------------------------------------------------------------

@trace()
def run_single_query_eval(query: str, session_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Modified version of run() that processes a single query and returns without interaction.
    Used for evaluation purposes.
    """
    # Create or load session
    if not session_id:
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    conversation_manager = ConversationManager(session_id)
    
    try:
        # Process the single query
        result = process_single_query(query, conversation_manager)
        
        # Save session state
        conversation_manager.save_session()
        
        return result
    except Exception as e:
        print(f"\n❌ Error: {e}")
        conversation_manager.save_session()
        raise

def main(inputs, ground_truths=None):
    """
    Function designed to be used with HoneyHive's evaluate.
    Uses the run function pattern as requested, but adapted for single query evaluation.
    
    Args:
        inputs: A dictionary containing the task/query and other metadata
        ground_truth: The expected result for evaluation (optional)
        
    Returns:
        The result of the multi-agent system's execution
    """
    # Extract the query from the input
    query = inputs.get("query") or inputs.get("task")
    if not query:
        return {"error": "No query or task provided"}
    
    # Create a unique session ID for this evaluation run
    session_id = f"eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(query) % 10000}"
    
    try:
        # Use the run pattern but for a single query
        result = run_single_query_eval(query, session_id)
        
        # Extract key information for evaluation
        return {
            "response": result["response"],
            "subtasks_count": len(result["decomposition"].subtasks),
            "agents_used": list(set(r["agent"] for r in result["task_results"].values())),
            "delegation_count": len(result["delegation_history"]),
            "task_breakdown": [
                {
                    "id": task.id,
                    "description": task.description,
                    "type": task.type.value,
                    "complexity": task.complexity
                }
                for task in result["decomposition"].subtasks
            ],
            "execution_details": {
                task_id: {
                    "agent": res["agent"],
                    "description": res["task_description"],
                    "tools_used": res["tools_used"],
                    "delegation_depth": res["delegation_depth"]
                }
                for task_id, res in result["task_results"].items()
            },
            "full_result": result  # Include the complete result for detailed analysis
        }
    except Exception as e:
        return {
            "error": str(e),
            "response": f"Error processing query: {str(e)}"
        }

def create_evaluation_dataset():
    """
    Create a dataset with example queries for testing the multi-agent system.
    
    Each item contains:
    - inputs: Dictionary with 'query' field containing the user's request
    - ground_truths: Dictionary with expected behavior metadata (for reference, not used in evaluation)
    """
    return [
        {
            "inputs": {
                "query": "Analyze the financial performance of Commonwealth Bank over the last 5 years and identify key growth drivers"
            },
            "ground_truths": {
                "expected_agents": ["financial_advisor", "data_analyst", "research_specialist"],
                "task_complexity": "high",
                "requires_delegation": True
            }
        },
        {
            "inputs": {
                "query": "Research the latest AI regulations in Australia and their potential impact on banking technology"
            },
            "ground_truths": {
                "expected_agents": ["research_specialist", "legal_advisor"],
                "task_complexity": "medium",
                "requires_web_search": True
            }
        },
        {
            "inputs": {
                "query": "Design a mobile banking app architecture that supports real-time fraud detection"
            },
            "ground_truths": {
                "expected_agents": ["technical_expert", "financial_advisor"],
                "task_complexity": "high",
                "requires_code": True
            }
        },
        {
            "inputs": {
                "query": "Create a marketing campaign for a new sustainable investment product targeting millennials"
            },
            "ground_truths": {
                "expected_agents": ["creative_writer", "financial_advisor", "research_specialist"],
                "task_complexity": "medium",
                "requires_creativity": True
            }
        },
        {
            "inputs": {
                "query": "What are the tax implications of crypto investments for Australian retail investors?"
            },
            "ground_truths": {
                "expected_agents": ["financial_advisor", "legal_advisor"],
                "task_complexity": "medium",
                "requires_research": True
            }
        }
    ]

def run_evaluation():
    """
    Run the evaluation using HoneyHive's evaluate function with an inline dataset.
    """
    # Create the evaluation dataset
    dataset = create_evaluation_dataset()
    
    print(f"Running evaluation with {len(dataset)} example queries:")
    for i, item in enumerate(dataset, 1):
        print(f"  {i}. {item['inputs']['query'][:80]}...")
    print()
    
    # Run the evaluation
    evaluate(
        function=main,
        api_key=HONEYHIVE_CONFIG['api_key'],
        project=HONEYHIVE_CONFIG['project'],
        name='Multi-Agent System Eval - GPT-5-Mini',
        dataset=dataset,  # Pass dataset directly instead of dataset_id
        evaluators=[],  # No evaluators as requested, server-side evaluators will handle it
        server_url=HONEYHIVE_CONFIG['server_url']
    )
    
    # Ensure all traces are flushed
    HoneyHiveTracer.flush()

# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    run_evaluation()
