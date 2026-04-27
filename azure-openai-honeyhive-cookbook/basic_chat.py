"""
This example demonstrates how to trace basic Azure OpenAI chat completions with HoneyHive.
"""
import os

from dotenv import load_dotenv
from openai import AzureOpenAI

from honeyhive import HoneyHiveTracer, trace
from openinference.instrumentation.openai import OpenAIInstrumentor

load_dotenv(override=True)

# Initialize HoneyHive tracer and OpenAI auto-instrumentation
tracer = HoneyHiveTracer.init(
    api_key=os.getenv("HH_API_KEY"),
    project=os.getenv("HH_PROJECT", "Azure-OpenAI-traces"),
)
OpenAIInstrumentor().instrument(tracer_provider=tracer.provider)

# Initialize Azure OpenAI client
client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version="2024-10-21",
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
)

DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "deployment-name")


@trace
def basic_chat_completion(question: str) -> str:
    """Make a simple chat completion call to Azure OpenAI API."""
    response = client.chat.completions.create(
        model=DEPLOYMENT,
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": question},
        ],
        temperature=0.7,
        max_tokens=150,
    )
    return response.choices[0].message.content


if __name__ == "__main__":
    for q in [
        "What is the capital of France?",
        "What are the three largest cities in Japan?",
    ]:
        answer = basic_chat_completion(q)
        print(f"Q: {q}")
        print(f"A: {answer}\n")

    print("View the traces in your HoneyHive dashboard!")
