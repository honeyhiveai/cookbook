"""
This example demonstrates how to trace OpenAI reasoning models with HoneyHive.
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
)
OpenAIInstrumentor().instrument(tracer_provider=tracer.provider)

# Initialize OpenAI client
client = OpenAI()


@trace
def call_reasoning_model(model: str, problem: str, effort: str = "medium") -> dict:
    """Call an OpenAI reasoning model (o1, o3-mini) with a given problem and effort level."""
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": problem},
        ],
        reasoning_effort=effort,
    )

    usage = response.usage
    reasoning_tokens = (
        usage.completion_tokens_details.reasoning_tokens
        if hasattr(usage, "completion_tokens_details") and usage.completion_tokens_details
        else None
    )

    return {
        "content": response.choices[0].message.content,
        "model": model,
        "reasoning_effort": effort,
        "usage": {
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "total_tokens": usage.total_tokens,
            "reasoning_tokens": reasoning_tokens,
        },
    }


if __name__ == "__main__":
    # Call o3-mini with a math problem
    result = call_reasoning_model(
        model="o3-mini",
        problem="Solve this step by step: Integrate x^3 * ln(x) with respect to x.",
        effort="medium",
    )
    print(f"Model: {result['model']} (effort={result['reasoning_effort']})")
    print(f"Response:\n{result['content']}")
    print(f"\nTokens — Total: {result['usage']['total_tokens']}, Reasoning: {result['usage']['reasoning_tokens']}")

    print("\nView the traces in your HoneyHive dashboard!")
