"""
This example demonstrates how to trace a multi-turn conversation with Azure OpenAI using HoneyHive.
"""
import os
from openai import AzureOpenAI
from honeyhive import HoneyHiveTracer, trace

# Initialize HoneyHive tracer at the beginning of your application
HoneyHiveTracer.init(
    api_key='your-honeyhive-api-key==',  # Replace with your actual HoneyHive API key
    project='Azure-OpenAI-traces',
    session_name="multi_turn_conversation"  # Set a descriptive session name
)

# Initialize Azure OpenAI client
client = AzureOpenAI(
    api_version="2023-07-01-preview",
    azure_endpoint="https://your-endpoint.openai.azure.com",  # Replace with your Azure endpoint
)

class Conversation:
    """
    Class to manage a conversation with the Azure OpenAI API.
    Each turn in the conversation is traced by HoneyHive.
    """
    def __init__(self, system_message="You are a helpful assistant."):
        self.messages = [{"role": "system", "content": system_message}]
        self.turn_count = 0
    
    @trace
    def add_user_message(self, content):
        """Add a user message to the conversation and get the assistant's response."""
        # Increment turn count
        self.turn_count += 1
        
        # Add user message to the conversation
        self.messages.append({"role": "user", "content": content})
        
        try:
            # Get assistant response
            response = client.chat.completions.create(
                model="deployment-name",  # Replace with your actual deployment name
                messages=self.messages,
                temperature=0.7,
                max_tokens=150
            )
            
            # Extract the assistant's message
            assistant_message = response.choices[0].message
            
            # Add assistant message to the conversation
            self.messages.append({"role": "assistant", "content": assistant_message.content})
            
            return {
                "role": assistant_message.role,
                "content": assistant_message.content,
                "turn": self.turn_count,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }
            }
        except Exception as e:
            print(f"Error in turn {self.turn_count}: {e}")
            raise
    
    def get_conversation_history(self):
        """Return the conversation history."""
        return self.messages[1:]  # Exclude the system message
    
    def get_current_turn(self):
        """Return the current turn count."""
        return self.turn_count

# Rich conversation with different topics
@trace
def run_rich_conversation():
    """Run a multi-turn conversation with the assistant on various topics."""
    # Initialize conversation with a broad system message
    conversation = Conversation(
        system_message="You are a knowledgeable assistant able to discuss a wide range of topics."
    )
    
    # First turn - Ask about a historical event
    turn1 = conversation.add_user_message("Can you tell me about the Apollo 11 mission?")
    print(f"Turn 1 - User: Can you tell me about the Apollo 11 mission?")
    print(f"Turn 1 - Assistant: {turn1['content']}\n")
    
    # Second turn - Follow up on the same topic
    turn2 = conversation.add_user_message("What were the names of the astronauts on that mission?")
    print(f"Turn 2 - User: What were the names of the astronauts on that mission?")
    print(f"Turn 2 - Assistant: {turn2['content']}\n")
    
    # Third turn - Change the topic
    turn3 = conversation.add_user_message("Let's switch topics. Can you explain how photosynthesis works?")
    print(f"Turn 3 - User: Let's switch topics. Can you explain how photosynthesis works?")
    print(f"Turn 3 - Assistant: {turn3['content']}\n")
    
    # Fourth turn - Ask for a summary of the conversation
    turn4 = conversation.add_user_message("Can you summarize what we've discussed so far?")
    print(f"Turn 4 - User: Can you summarize what we've discussed so far?")
    print(f"Turn 4 - Assistant: {turn4['content']}\n")
    
    return conversation.get_conversation_history()

# Technical support conversation with function calling
@trace
def run_tech_support_conversation():
    """Run a technical support conversation with the assistant."""
    # Initialize conversation with a technical support system message
    conversation = Conversation(
        system_message="You are a technical support assistant helping users with computer problems."
    )
    
    # First turn - Initial problem statement
    turn1 = conversation.add_user_message("My laptop won't turn on. The power light blinks once when I press the power button, then nothing happens.")
    print(f"Tech Support Turn 1 - User: My laptop won't turn on. The power light blinks once when I press the power button, then nothing happens.")
    print(f"Tech Support Turn 1 - Assistant: {turn1['content']}\n")
    
    # Second turn - Provide additional information
    turn2 = conversation.add_user_message("Yes, I've tried plugging it in. The charger light is on, and the laptop was working fine yesterday.")
    print(f"Tech Support Turn 2 - User: Yes, I've tried plugging it in. The charger light is on, and the laptop was working fine yesterday.")
    print(f"Tech Support Turn 2 - Assistant: {turn2['content']}\n")
    
    # Third turn - Follow instructions
    turn3 = conversation.add_user_message("I removed the battery and held the power button for 30 seconds as you suggested, then reconnected everything. Now it's starting up! What caused this issue?")
    print(f"Tech Support Turn 3 - User: I removed the battery and held the power button for 30 seconds as you suggested, then reconnected everything. Now it's starting up! What caused this issue?")
    print(f"Tech Support Turn 3 - Assistant: {turn3['content']}\n")
    
    return conversation.get_conversation_history()

if __name__ == "__main__":
    # Run the rich conversation
    print("=== Rich Conversation ===")
    rich_convo_history = run_rich_conversation()
    
    print("\n" + "="*50 + "\n")
    
    # Run the technical support conversation
    print("=== Technical Support Conversation ===")
    tech_support_history = run_tech_support_conversation()
    
    # You can view the traces in your HoneyHive dashboard
    print("\nView the conversation traces in your HoneyHive dashboard!")
    print(f"Total exchanges: {len(rich_convo_history) // 2 + len(tech_support_history) // 2}") 