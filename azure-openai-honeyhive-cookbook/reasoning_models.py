"""
This example demonstrates how to trace Azure OpenAI reasoning models with HoneyHive.
Note: Availability of specific reasoning models may depend on your Azure OpenAI deployment.
"""
import os
from openai import AzureOpenAI
from honeyhive import HoneyHiveTracer, trace

# Initialize HoneyHive tracer at the beginning of your application
HoneyHiveTracer.init(
    api_key='your-honeyhive-api-key==',  # Replace with your actual HoneyHive API key
    project='Azure-OpenAI-traces'
)

# Initialize Azure OpenAI client
client = AzureOpenAI(
    api_version="2023-07-01-preview",
    azure_endpoint="https://your-endpoint.openai.azure.com",  # Replace with your Azure endpoint
)

# Trace reasoning model call for complex math problems
@trace
def call_reasoning_model_math():
    """
    Demonstrate calling a reasoning-capable model for math problems and trace the request/response.
    Note: Use your Azure OpenAI deployed model that supports advanced reasoning.
    """
    try:
        # Complex math problem that benefits from reasoning capability
        response = client.chat.completions.create(
            model="gpt-4-deployment",  # Replace with your actual GPT-4 deployment name
            messages=[
                {"role": "system", "content": "You are a helpful math assistant."},
                {"role": "user", "content": "Solve this step by step: Integrate x^3 * ln(x) with respect to x."}
            ],
            temperature=0.1  # Lower temperature for more precise reasoning
        )
        
        # Extract the response and the usage information
        content = response.choices[0].message.content
        
        return {
            "content": content,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
        }
    except Exception as e:
        print(f"Error: {e}")
        raise

# Trace reasoning model call for code optimization
@trace
def call_reasoning_model_code():
    """
    Demonstrate calling a reasoning model for code optimization tasks.
    """
    try:
        # A code refactoring task that benefits from reasoning capability
        response = client.chat.completions.create(
            model="gpt-4-deployment",  # Replace with your actual GPT-4 deployment name
            messages=[
                {"role": "system", "content": "You are a helpful programming assistant."},
                {"role": "user", "content": """
                Refactor this Python code to be more efficient and readable:
                
                def fibonacci(n):
                    if n <= 0:
                        return 0
                    elif n == 1:
                        return 1
                    else:
                        return fibonacci(n-1) + fibonacci(n-2)
                
                print(fibonacci(30))
                """}
            ],
            temperature=0.2  # Low temperature for code tasks
        )
        
        # Extract the response and the usage information
        content = response.choices[0].message.content
        
        return {
            "content": content,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
        }
    except Exception as e:
        print(f"Error: {e}")
        raise

# Testing different temperature settings for reasoning tasks
@trace
def call_model_with_temperature(problem, temperature=0.2):
    """
    Demonstrate calling the model with different temperature settings.
    
    Args:
        problem: Math problem to solve
        temperature: Model temperature (0.0 to 1.0)
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4-deployment",  # Replace with your actual GPT-4 deployment name
            messages=[
                {"role": "system", "content": "You are a helpful math assistant."},
                {"role": "user", "content": f"Solve this step by step: {problem}"}
            ],
            temperature=temperature,
            max_tokens=1000  # Limit the number of tokens generated
        )
        
        # Extract the response and the usage information
        content = response.choices[0].message.content
        
        return {
            "content": content,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
                "temperature": temperature
            }
        }
    except Exception as e:
        print(f"Error: {e}")
        raise

if __name__ == "__main__":
    # Call reasoning model for math problems
    print("Calling reasoning model for integral problem...")
    math_result = call_reasoning_model_math()
    print(f"Response for math problem:")
    print(math_result["content"])
    print(f"\nToken usage - Total: {math_result['usage']['total_tokens']}")
    
    print("\n" + "="*50 + "\n")
    
    # Call reasoning model for code refactoring
    print("Calling reasoning model for code refactoring...")
    code_result = call_reasoning_model_code()
    print(f"Response for code refactoring:")
    print(code_result["content"])
    print(f"\nToken usage - Total: {code_result['usage']['total_tokens']}")
    
    print("\n" + "="*50 + "\n")
    
    # Demonstrate different temperature settings
    print("Comparing different temperature settings...")
    
    # Low temperature for precise reasoning
    quadratic_problem = "Solve the quadratic equation: 2x^2 - 7x + 3 = 0"
    low_temp_result = call_model_with_temperature(quadratic_problem, 0.1)
    
    # Higher temperature for more creative approaches
    complex_problem = "Find all values of x that satisfy the equation: sin(x) + cos(x) = 1"
    high_temp_result = call_model_with_temperature(complex_problem, 0.7)
    
    # Print comparison
    print(f"Low temperature (Quadratic equation) - Temperature: {low_temp_result['usage']['temperature']}")
    print(f"Low temperature result: {low_temp_result['content'][:200]}...")
    print(f"\nHigh temperature (Trigonometric equation) - Temperature: {high_temp_result['usage']['temperature']}")
    print(f"High temperature result: {high_temp_result['content'][:200]}...")
    
    # You can view the traces in your HoneyHive dashboard
    print("\nView the traces in your HoneyHive dashboard!") 