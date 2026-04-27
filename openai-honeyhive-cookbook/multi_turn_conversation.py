"""
This example demonstrates how to trace a multi-turn conversation with OpenAI using HoneyHive.
"""
import os

from dotenv import load_dotenv
from openai import OpenAI

from honeyhive import HoneyHiveTracer, trace
from openinference.instrumentation.openai import OpenAIInstrumentor

load_dotenv(override=True)

# Initialize HoneyHive tracer and OpenAI auto-instrumentation
tracer = HoneyHiveTracer.init(
    api_key=os.getenv("HH_API_KEY"),
    project=os.getenv("HH_PROJECT", "OpenAI-traces"),
    session_name="multi_turn_conversation",
)
OpenAIInstrumentor().instrument(tracer_provider=tracer.provider)

# Initialize OpenAI client
client = OpenAI()


class Conversation:
    """Manages a multi-turn conversation with the OpenAI API."""

    def __init__(self, system_message="You are a helpful assistant."):
        self.messages = [{"role": "system", "content": system_message}]

    @trace
    def chat(self, user_message: str) -> str:
        """Send a user message and return the assistant's response."""
        self.messages.append({"role": "user", "content": user_message})

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=self.messages,
            temperature=0.7,
            max_tokens=150,
        )

        reply = response.choices[0].message.content
        self.messages.append({"role": "assistant", "content": reply})
        return reply


@trace
def run_conversation():
    """Run a multi-turn conversation demonstrating context retention."""
    convo = Conversation(
        system_message="You are a knowledgeable assistant able to discuss a wide range of topics."
    )

    exchanges = [
        "Can you tell me about the Apollo 11 mission?",
        "What were the names of the astronauts on that mission?",
        "Let's switch topics. Can you explain how photosynthesis works?",
        "Can you summarize what we've discussed so far?",
    ]

    for user_msg in exchanges:
        print(f"User: {user_msg}")
        reply = convo.chat(user_msg)
        print(f"Assistant: {reply}\n")


if __name__ == "__main__":
    run_conversation()
    print("View the conversation traces in your HoneyHive dashboard!")
