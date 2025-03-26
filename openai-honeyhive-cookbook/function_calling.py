"""
This example demonstrates how to trace OpenAI function calling with HoneyHive.
"""
import os
import json
from openai import OpenAI
from honeyhive import HoneyHiveTracer, trace

# Initialize HoneyHive tracer at the beginning of your application
HoneyHiveTracer.init(
    api_key='your-honeyhive-api-key==',  # Replace with your actual HoneyHive API key
    project='OpenAI-traces'
)

# Initialize OpenAI client
client = OpenAI(
    api_key='your-openai-key'  # Replace with your actual OpenAI API key
)

# Define a weather function that will be called by the model
@trace
def get_weather(location, unit="celsius"):
    """
    Get the current weather in a given location.
    This is a mock function that would typically call a weather API.
    """
    # In a real application, you would call a weather API here
    # For demo purposes, we'll just return mock data
    weather_data = {
        "location": location,
        "temperature": 22 if unit == "celsius" else 72,
        "unit": unit,
        "forecast": ["sunny", "windy"],
        "humidity": 60
    }
    return weather_data

# Function to demonstrate basic function calling
@trace
def basic_function_calling():
    """
    Demonstrate basic function calling with OpenAI API.
    The model will decide when to call the function based on the user query.
    """
    # Define the tools (functions) the model can use
    tools = [
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
                            "description": "The city and country, e.g., 'San Francisco, CA' or 'Paris, France'"
                        },
                        "unit": {
                            "type": "string",
                            "enum": ["celsius", "fahrenheit"],
                            "description": "The temperature unit to use. Default is celsius."
                        }
                    },
                    "required": ["location"]
                }
            }
        }
    ]
    
    # Make a request to the OpenAI API
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What's the weather like in Paris today?"}
    ]
    
    # This API call will be traced by HoneyHive
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        tools=tools,
        tool_choice="auto"
    )
    
    response_message = response.choices[0].message
    
    # Process the response based on whether a function was called
    if response_message.tool_calls:
        # Extract function call details
        function_calls = []
        for tool_call in response_message.tool_calls:
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)
            
            # Execute the function
            if function_name == "get_weather":
                function_response = get_weather(
                    location=function_args.get("location"),
                    unit=function_args.get("unit", "celsius")
                )
                function_calls.append({
                    "name": function_name,
                    "arguments": function_args,
                    "response": function_response
                })
            
            # Add the function response to messages
            messages.append(response_message)
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(function_response)
            })
        
        # Get the final response from the assistant
        second_response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages
        )
        
        return {
            "initial_response": response_message,
            "function_calls": function_calls,
            "final_response": second_response.choices[0].message.content
        }
    else:
        # No function was called
        return {
            "response": response_message.content,
            "function_calls": []
        }

# Function calling with multiple functions
@trace
def multi_function_calling():
    """
    Demonstrate function calling with multiple available functions.
    """
    # Define multiple tools (functions) the model can use
    tools = [
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
                            "description": "The city and country"
                        },
                        "unit": {
                            "type": "string",
                            "enum": ["celsius", "fahrenheit"],
                            "description": "The temperature unit to use. Default is celsius."
                        }
                    },
                    "required": ["location"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "search_hotels",
                "description": "Search for hotels in a specified location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "The city and country"
                        },
                        "check_in": {
                            "type": "string",
                            "description": "Check-in date in YYYY-MM-DD format"
                        },
                        "check_out": {
                            "type": "string",
                            "description": "Check-out date in YYYY-MM-DD format"
                        }
                    },
                    "required": ["location"]
                }
            }
        }
    ]
    
    # Make a request to the OpenAI API
    messages = [
        {"role": "system", "content": "You are a helpful travel assistant."},
        {"role": "user", "content": "I'm planning a trip to Tokyo next week. What's the weather like and can you recommend some hotels?"}
    ]
    
    # This API call will be traced by HoneyHive
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        tools=tools,
        tool_choice="auto"
    )
    
    # This would continue with handling function calls as in the previous example
    # For brevity, we'll just return the initial response
    return {
        "response": response.choices[0].message,
        "tools_available": [tool["function"]["name"] for tool in tools]
    }

if __name__ == "__main__":
    # Test basic function calling
    result = basic_function_calling()
    print("Basic Function Calling Result:")
    if "final_response" in result:
        print(f"Final response: {result['final_response']}")
        print(f"Functions called: {[fc['name'] for fc in result['function_calls']]}")
    else:
        print(f"Response: {result['response']}")
    
    # Test multi-function calling
    print("\nMulti-Function Calling Result:")
    multi_result = multi_function_calling()
    print(f"Response: {multi_result['response']}")
    print(f"Available tools: {multi_result['tools_available']}")
    
    # You can view the traces in your HoneyHive dashboard
    print("\nView the traces in your HoneyHive dashboard!") 