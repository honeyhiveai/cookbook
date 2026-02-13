"""
Wealth Advisory Session Management and Main Workflow
"""

import pickle
from datetime import datetime
from typing import Dict, Any, Optional
from honeyhive.tracer.custom import trace
from registry import ConversationContext
from orchestration import ClientAdvisoryOrchestrator

# ---------------------------------------------------------------------------
# Client Advisory Session Manager
# ---------------------------------------------------------------------------

class AdvisorySessionManager:
    """Manages multi-turn client advisory sessions with context memory."""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.context = ConversationContext(
            conversation_id=session_id,
            turns=[],
            user_preferences={},
            task_outcomes={},
            active_agents=[]
        )
        self.max_context_turns = 10
    
    @trace()
    def add_turn(self, client_inquiry: str, response: str, metadata: Dict[str, Any]):
        """Add an advisory conversation turn to history."""
        turn = {
            "timestamp": datetime.now().isoformat(),
            "user_input": client_inquiry,
            "response": response,
            "metadata": metadata
        }
        self.context.turns.append(turn)
        
        # Keep only recent turns in context
        if len(self.context.turns) > self.max_context_turns:
            self.context.turns = self.context.turns[-self.max_context_turns:]
    
    @trace()
    def update_preferences(self, preferences: Dict[str, Any]):
        """Update client investment preferences based on interactions."""
        self.context.user_preferences.update(preferences)
    
    @trace()
    def get_relevant_context(self, query: str) -> str:
        """Get relevant context for current client inquiry."""
        if not self.context.turns:
            return ""
        
        # Simple relevance: just return last 3 turns
        # In production, use embedding similarity
        recent_turns = self.context.turns[-3:]
        context_str = "Previous advisory conversation:\n"
        for turn in recent_turns:
            context_str += f"Client: {turn['user_input'][:100]}...\n"
            context_str += f"Advisor: {turn['response'][:100]}...\n\n"
        
        return context_str
    
    def save_session(self):
        """Save advisory session to disk."""
        with open(f"advisory_session_{self.session_id}.pkl", "wb") as f:
            pickle.dump(self.context, f)
    
    def load_session(self):
        """Load advisory session from disk."""
        try:
            with open(f"advisory_session_{self.session_id}.pkl", "rb") as f:
                self.context = pickle.load(f)
        except FileNotFoundError:
            pass

# ---------------------------------------------------------------------------
# Main Wealth Advisory Workflow
# ---------------------------------------------------------------------------

@trace()
def process_client_inquiry(query: str, session_manager: AdvisorySessionManager) -> Dict[str, Any]:
    """Process a client inquiry through the wealth advisory multi-agent system."""
    
    orchestrator = ClientAdvisoryOrchestrator()
    
    # Get relevant context from previous interactions
    context_str = session_manager.get_relevant_context(query)
    if context_str:
        print(f"\n📚 Using context from previous advisory sessions...")
    
    # Process inquiry through orchestration
    result = orchestrator.orchestrate_advisory_workflow(query, session_manager.context)
    
    # Update conversation history
    session_manager.add_turn(
        query,
        result["response"],
        {
            "subtasks": len(result["decomposition"].subtasks),
            "agents_used": list(set(r["agent"] for r in result["task_results"].values())),
            "delegations": len(result["delegation_history"])
        }
    )
    
    # Learn from interaction - detect client investment interests
    query_lower = query.lower()
    if any(term in query_lower for term in ["retirement", "pension", "401k"]):
        session_manager.update_preferences({"interest": "retirement_planning"})
    if any(term in query_lower for term in ["esg", "sustainable", "impact"]):
        session_manager.update_preferences({"interest": "esg_investing"})
    if any(term in query_lower for term in ["tax", "tax-efficient"]):
        session_manager.update_preferences({"interest": "tax_optimization"})
    if any(term in query_lower for term in ["risk", "conservative", "volatile"]):
        session_manager.update_preferences({"risk_sensitivity": "high"})
    
    return result

@trace()
def run_advisory_session(session_manager: AdvisorySessionManager):
    """Run the interactive wealth advisory session loop."""
    
    print("=== Universal Bank Wealth Advisory Platform ===")
    print("Specialist Team:")
    print("- Market Intelligence Analyst")
    print("- Quantitative Analyst")
    print("- Wealth Strategist")
    print("- FinTech Solutions Architect")
    print("- Client Communications Specialist")
    print("- Regulatory Compliance Officer")
    print("\nType 'exit' to end the session\n")
    
    while True:
        user_input = input("\n💬 Client Inquiry: ").strip()
        if user_input.lower() in ['exit', 'quit', 'bye']:
            print("\n👋 Ending advisory session. Saving session state...")
            session_manager.save_session()
            break
        
        if not user_input:
            continue
        
        print("\n🔄 Processing your inquiry with our specialist team...")
        
        try:
            result = process_client_inquiry(user_input, session_manager)
            
            # Display response
            print("\n✅ Advisory Response:")
            print("-" * 80)
            print(result["response"])
            print("-" * 80)
            
            # Show delegation history if any
            if result["delegation_history"]:
                print("\n🔄 Specialist collaboration chain:")
                for delegation in result["delegation_history"]:
                    print(f"  {delegation.from_agent} → {delegation.to_agent}: {delegation.reason}")
        
        except Exception as e:
            print(f"\n❌ Error processing inquiry: {e}")
            import traceback
            traceback.print_exc()

@trace()
def run(session_id: Optional[str] = None):
    """Main entry point for running the wealth advisory platform."""
    
    # Create or load session
    if not session_id:
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        print(f"Starting new advisory session: {session_id}")
    else:
        print(f"Loading advisory session: {session_id}")
    
    session_manager = AdvisorySessionManager(session_id)
    session_manager.load_session()
    
    try:
        run_advisory_session(session_manager)
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted. Saving session...")
        session_manager.save_session()
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        session_manager.save_session()
        raise

# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from honeyhive.tracer import HoneyHiveTracer
    from config import HONEYHIVE_CONFIG

    # Initialize HoneyHive at the beginning of main
    HoneyHiveTracer.init(**HONEYHIVE_CONFIG)

    # Run interactive advisory session (type 'exit' to end)
    run()


# Backward compatibility aliases
ConversationManager = AdvisorySessionManager
process_single_query = process_client_inquiry
