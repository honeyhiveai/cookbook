"""
This example demonstrates how to trace OpenAI function calling with HoneyHive.
"""
import json
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

# Tool definitions
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather in a specified location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "The city and country, e.g., 'Paris, France'",
                    },
                    "unit": {
                        "type": "string",
                        "enum": ["celsius", "fahrenheit"],
                        "description": "The temperature unit to use.",
                    },
                },
                "required": ["location"],
            },
        },
    }
]


# Mock tool implementation
@trace
def get_weather(location: str, unit: str = "celsius") -> dict:
    """Get the current weather in a given location (mock)."""
    return {
        "location": location,
        "temperature": 22 if unit == "celsius" else 72,
        "unit": unit,
        "forecast": ["sunny", "windy"],
        "humidity": 60,
    }


TOOL_FUNCTIONS = {"get_weather": get_weather}


@trace
def function_calling_demo():
    """Demonstrate function calling: model decides to call a tool, we execute it, then get a final answer."""
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What's the weather like in Paris today?"},
    ]

    # First call — model may request tool use
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        tools=TOOLS,
        tool_choice="auto",
    )
    assistant_msg = response.choices[0].message

    if not assistant_msg.tool_calls:
        return assistant_msg.content

    # Process each tool call
    messages.append(assistant_msg)
    for tool_call in assistant_msg.tool_calls:
        fn_name = tool_call.function.name
        fn_args = json.loads(tool_call.function.arguments)
        result = TOOL_FUNCTIONS[fn_name](**fn_args)
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": json.dumps(result),
        })

    # Second call — model synthesizes the tool results
    final = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
    )
    return final.choices[0].message.content


if __name__ == "__main__":
    answer = function_calling_demo()
    print(f"Final response: {answer}")
    print("\nView the traces in your HoneyHive dashboard!")
