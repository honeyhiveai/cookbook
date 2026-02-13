"""
Wealth Advisory Platform - HoneyHive Evaluation Setup
=====================================================
This evaluation module tests the multi-agent wealth advisory system with
realistic client scenarios covering portfolio analysis, investment strategy,
compliance checks, and client communications.

USAGE:
------
Evaluation Mode (HoneyHive):
   python evaluation.py
   
   The evaluation will run with 5 pre-defined client scenarios that test:
   - Portfolio review and rebalancing recommendations
   - Market impact analysis on client allocations
   - ESG investment recommendations for HNW clients
   - Suitability and compliance verification
   - Client communication drafting
"""

from datetime import datetime
from typing import Dict, Any, Optional
from honeyhive.tracer import HoneyHiveTracer
from honeyhive.tracer.custom import trace
from honeyhive import evaluate

# Import all components from our refactored modules
from config import HONEYHIVE_CONFIG
from registry import ConversationContext
from main import AdvisorySessionManager, process_client_inquiry

# ---------------------------------------------------------------------------
# HoneyHive Evaluation Functions
# ---------------------------------------------------------------------------

@trace()
def run_single_advisory_eval(query: str, session_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Process a single client inquiry for evaluation purposes.
    Returns structured results for HoneyHive evaluation.
    """
    # Create or load session
    if not session_id:
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    session_manager = AdvisorySessionManager(session_id)
    
    try:
        # Process the client inquiry
        result = process_client_inquiry(query, session_manager)
        
        # Save session state
        session_manager.save_session()
        
        return result
    except Exception as e:
        print(f"\n❌ Error: {e}")
        session_manager.save_session()
        raise


def main(inputs, ground_truths=None):
    """
    Function designed to be used with HoneyHive's evaluate.
    Processes wealth advisory client inquiries through the multi-agent system.
    
    Args:
        inputs: A dictionary containing the client inquiry and other metadata
        ground_truths: Expected behavior metadata for evaluation (optional)
        
    Returns:
        Structured results from the wealth advisory system
    """
    # Extract the query from the input
    query = inputs.get("query") or inputs.get("task")
    if not query:
        return {"error": "No client inquiry provided"}
    
    # Create a unique session ID for this evaluation run
    session_id = f"eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(query) % 10000}"
    
    try:
        # Process the client inquiry
        result = run_single_advisory_eval(query, session_id)
        
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
            "response": f"Error processing client inquiry: {str(e)}"
        }


def create_evaluation_dataset():
    """
    Create a dataset with wealth advisory client scenarios for testing.
    
    Each scenario represents a realistic client inquiry that tests
    different aspects of the multi-agent wealth advisory system.
    """
    return [
        {
            "inputs": {
                "query": "Review the Smith family portfolio and recommend rebalancing strategies given their upcoming retirement in 5 years. They currently have a 70/30 equity-bond split with significant concentration in tech stocks."
            },
            "ground_truths": {
                "expected_agents": ["quantitative_analyst", "wealth_strategist"],
                "task_complexity": "high",
                "scenario_type": "portfolio_review",
                "requires_risk_analysis": True
            }
        },
        {
            "inputs": {
                "query": "Analyze the impact of the Federal Reserve's recent interest rate decisions on our clients' fixed income allocations. What adjustments should we recommend for clients with significant bond exposure?"
            },
            "ground_truths": {
                "expected_agents": ["market_intelligence_analyst", "wealth_strategist"],
                "task_complexity": "medium",
                "scenario_type": "market_analysis",
                "requires_market_research": True
            }
        },
        {
            "inputs": {
                "query": "Recommend suitable ESG-focused investment options for a risk-averse high-net-worth client with $5M AUM who wants to align their portfolio with environmental and social values while maintaining capital preservation."
            },
            "ground_truths": {
                "expected_agents": ["wealth_strategist", "regulatory_compliance_officer", "market_intelligence_analyst"],
                "task_complexity": "high",
                "scenario_type": "investment_recommendation",
                "requires_compliance_check": True
            }
        },
        {
            "inputs": {
                "query": "Verify the suitability of a concentrated stock position (40% in single company) for a client with a moderate risk profile and 15-year investment horizon. What are the compliance considerations and recommended actions?"
            },
            "ground_truths": {
                "expected_agents": ["regulatory_compliance_officer", "quantitative_analyst"],
                "task_complexity": "high",
                "scenario_type": "compliance_review",
                "requires_suitability_analysis": True
            }
        },
        {
            "inputs": {
                "query": "Draft a quarterly investment review letter for our wealth management clients explaining recent market volatility, our portfolio positioning, and outlook for the next quarter. The tone should be reassuring yet professional."
            },
            "ground_truths": {
                "expected_agents": ["client_communications_specialist", "market_intelligence_analyst"],
                "task_complexity": "medium",
                "scenario_type": "client_communication",
                "requires_market_context": True
            }
        }
    ]


def run_evaluation():
    """
    Run the evaluation using HoneyHive's evaluate function with wealth advisory scenarios.
    """
    # Create the evaluation dataset
    dataset = create_evaluation_dataset()
    
    print("=" * 80)
    print("Universal Bank Wealth Advisory Platform - HoneyHive Evaluation")
    print("=" * 80)
    print(f"\nRunning evaluation with {len(dataset)} client scenarios:\n")
    
    for i, item in enumerate(dataset, 1):
        scenario_type = item['ground_truths'].get('scenario_type', 'general')
        print(f"  {i}. [{scenario_type.upper()}] {item['inputs']['query'][:70]}...")
    
    print("\n" + "=" * 80 + "\n")
    
    # Run the evaluation
    evaluate(
        function=main,
        api_key=HONEYHIVE_CONFIG['api_key'],
        project=HONEYHIVE_CONFIG['project'],
        name='Wealth Advisory Platform Eval',
        dataset=dataset,  # Pass dataset directly instead of dataset_id
        evaluators=[],  # Server-side evaluators will handle evaluation
        server_url=HONEYHIVE_CONFIG['server_url']
    )
    
    # Ensure all traces are flushed
    HoneyHiveTracer.flush()
    
    print("\n" + "=" * 80)
    print("Evaluation complete. View results in HoneyHive dashboard.")
    print("=" * 80)


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    run_evaluation()
