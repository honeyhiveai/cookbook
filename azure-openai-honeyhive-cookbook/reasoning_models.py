"""
This example demonstrates how to trace Azure OpenAI reasoning models with HoneyHive.
Note: Availability of specific reasoning models depends on your Azure OpenAI deployment.
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

DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4-deployment")


@trace
def call_reasoning_model(problem: str, temperature: float = 0.1) -> dict:
    """Call an Azure OpenAI model with a reasoning-heavy problem."""
    response = client.chat.completions.create(
        model=DEPLOYMENT,
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": problem},
        ],
        temperature=temperature,
    )

    return {
        "content": response.choices[0].message.content,
        "usage": {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens,
        },
    }


if __name__ == "__main__":
    result = call_reasoning_model(
        "Solve this step by step: Integrate x^3 * ln(x) with respect to x."
    )
    print(f"Response:\n{result['content']}")
    print(f"\nTokens — Total: {result['usage']['total_tokens']}")

    print("\nView the traces in your HoneyHive dashboard!")
