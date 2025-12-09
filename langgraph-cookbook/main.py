"""
Conversation Management and Main Workflow
"""

import pickle
from datetime import datetime
from typing import Dict, Any, Optional
from honeyhive.tracer.custom import trace
from registry import ConversationContext
from orchestration import PrincipalRouterAgent

# ---------------------------------------------------------------------------
# Conversation Manager
# ---------------------------------------------------------------------------

class ConversationManager:
    """Manages multi-turn conversations with memory."""
    
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
    def add_turn(self, user_input: str, response: str, metadata: Dict[str, Any]):
        """Add a conversation turn to history."""
        turn = {
            "timestamp": datetime.now().isoformat(),
            "user_input": user_input,
            "response": response,
            "metadata": metadata
        }
        self.context.turns.append(turn)
        
        # Keep only recent turns in context
        if len(self.context.turns) > self.max_context_turns:
            self.context.turns = self.context.turns[-self.max_context_turns:]
    
    @trace()
    def update_preferences(self, preferences: Dict[str, Any]):
        """Update user preferences based on interactions."""
        self.context.user_preferences.update(preferences)
    
    @trace()
    def get_relevant_context(self, query: str) -> str:
        """Get relevant context for current query."""
        if not self.context.turns:
            return ""
        
        # Simple relevance: just return last 3 turns
        # In production, use embedding similarity
        recent_turns = self.context.turns[-3:]
        context_str = "Previous conversation:\n"
        for turn in recent_turns:
            context_str += f"User: {turn['user_input'][:100]}...\n"
            context_str += f"Assistant: {turn['response'][:100]}...\n\n"
        
        return context_str
    
    def save_session(self):
        """Save session to disk."""
        with open(f"session_{self.session_id}.pkl", "wb") as f:
            pickle.dump(self.context, f)
    
    def load_session(self):
        """Load session from disk."""
        try:
            with open(f"session_{self.session_id}.pkl", "rb") as f:
                self.context = pickle.load(f)
        except FileNotFoundError:
            pass

# ---------------------------------------------------------------------------
# Main Enhanced Workflow
# ---------------------------------------------------------------------------

@trace()
def process_single_query(query: str, conversation_manager: ConversationManager) -> Dict[str, Any]:
    """Process a single user query through the multi-agent system."""
    
    principal_router = PrincipalRouterAgent()
    
    # Get relevant context
    context_str = conversation_manager.get_relevant_context(query)
    if context_str:
        print(f"\n📚 Using context from previous turns...")
    
    # Process query through orchestration
    result = principal_router.orchestrate_multi_agent_workflow(query, conversation_manager.context)
    
    # Update conversation history
    conversation_manager.add_turn(
        query,
        result["response"],
        {
            "subtasks": len(result["decomposition"].subtasks),
            "agents_used": list(set(r["agent"] for r in result["task_results"].values())),
            "delegations": len(result["delegation_history"])
        }
    )
    
    # Learn from interaction (simplified)
    if "financial" in query.lower():
        conversation_manager.update_preferences({"interest": "finance"})
    if "technical" in query.lower():
        conversation_manager.update_preferences({"interest": "technology"})
    
    return result

@trace()
def run_conversation_loop(conversation_manager: ConversationManager):
    """Run the interactive conversation loop."""
    
    print("=== CommBank Enhanced Multi-Agent System ===")
    print("Features:")
    print("- LLM-powered task decomposition and routing")
    print("- Dynamic agent selection based on capabilities")
    print("- Advanced nested delegation patterns")
    print("- Multi-turn conversation support")
    print("- Rich tool ecosystem")
    print("\nType 'exit' to end the conversation\n")
    
    while True:
        user_input = input("\n💬 You: ").strip()
        if user_input.lower() in ['exit', 'quit', 'bye']:
            print("\n👋 Ending conversation. Saving session...")
            conversation_manager.save_session()
            break
        
        if not user_input:
            continue
        
        print("\n🔄 Processing your request...")
        
        try:
            result = process_single_query(user_input, conversation_manager)
            
            # Display response
            print("\n✅ Response:")
            print("-" * 80)
            print(result["response"])
            print("-" * 80)
            
            # Show delegation history if any
            if result["delegation_history"]:
                print("\n🔄 Delegation chain:")
                for delegation in result["delegation_history"]:
                    print(f"  {delegation.from_agent} → {delegation.to_agent}: {delegation.reason}")
        
        except Exception as e:
            print(f"\n❌ Error processing query: {e}")
            import traceback
            traceback.print_exc()

@trace()
def run(session_id: Optional[str] = None):
    """Main entry point for running the enhanced multi-agent system."""
    
    # Create or load session
    if not session_id:
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        print(f"Starting new session: {session_id}")
    else:
        print(f"Loading session: {session_id}")
    
    conversation_manager = ConversationManager(session_id)
    conversation_manager.load_session()
    
    try:
        run_conversation_loop(conversation_manager)
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted. Saving session...")
        conversation_manager.save_session()
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        conversation_manager.save_session()
        raise

# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    from honeyhive.tracer import HoneyHiveTracer
    from config import HONEYHIVE_CONFIG
    
    # Initialize HoneyHive at the beginning of main function
    HoneyHiveTracer.init(**HONEYHIVE_CONFIG)
    
    # For testing purposes, run a simple query instead of interactive mode
    conversation_manager = ConversationManager("test_session")
    
    # Test query
    test_query = "What are the current stock market trends for tech companies?"
    print(f"Testing with query: {test_query}")
    
    try:
        result = process_single_query(test_query, conversation_manager)
        print("\n✅ Response:")
        print("-" * 80)
        print(result["response"])
        print("-" * 80)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
