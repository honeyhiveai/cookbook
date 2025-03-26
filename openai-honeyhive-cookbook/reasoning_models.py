"""
This example demonstrates how to trace OpenAI reasoning models with HoneyHive.
"""
import os
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

# Trace reasoning model call with o1 model
@trace
def call_o1_model():
    """
    Demonstrate calling the o1 reasoning model and trace the request/response.
    """
    try:
        # Complex math problem that benefits from reasoning capability
        response = client.chat.completions.create(
            model="o1",
            messages=[
                {"role": "system", "content": "You are a helpful math assistant."},
                {"role": "user", "content": "Solve this step by step: Integrate x^3 * ln(x) with respect to x."}
            ],
            reasoning_effort="high"  # Use high reasoning effort for complex problems
        )
        
        # Extract the response and the usage information
        content = response.choices[0].message.content
        reasoning_tokens = response.usage.completion_tokens_details.reasoning_tokens if hasattr(response.usage, "completion_tokens_details") else None
        
        return {
            "content": content,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
                "reasoning_tokens": reasoning_tokens
            }
        }
    except Exception as e:
        print(f"Error: {e}")
        raise

# Trace reasoning model call with o3-mini model
@trace
def call_o3_mini_model():
    """
    Demonstrate calling the o3-mini reasoning model and trace the request/response.
    """
    try:
        # A code refactoring task that benefits from reasoning capability
        response = client.chat.completions.create(
            model="o3-mini",
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
            reasoning_effort="medium"  # Use medium reasoning effort for this task
        )
        
        # Extract the response and the usage information
        content = response.choices[0].message.content
        reasoning_tokens = response.usage.completion_tokens_details.reasoning_tokens if hasattr(response.usage, "completion_tokens_details") else None
        
        return {
            "content": content,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
                "reasoning_tokens": reasoning_tokens
            }
        }
    except Exception as e:
        print(f"Error: {e}")
        raise

# Testing different reasoning efforts with o1 model
@trace
def call_o1_model_with_effort(problem, effort="medium"):
    """
    Demonstrate calling the o1 model with different reasoning efforts.
    
    Args:
        problem: Math problem to solve
        effort: Reasoning effort ('low', 'medium', or 'high')
    """
    try:
        response = client.chat.completions.create(
            model="o1",
            messages=[
                {"role": "system", "content": "You are a helpful math assistant."},
                {"role": "user", "content": f"Solve this step by step: {problem}"}
            ],
            reasoning_effort=effort,
            max_completion_tokens=1000  # Limit the number of tokens generated
        )
        
        # Extract the response and the usage information
        content = response.choices[0].message.content
        reasoning_tokens = response.usage.completion_tokens_details.reasoning_tokens if hasattr(response.usage, "completion_tokens_details") else None
        
        return {
            "content": content,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
                "reasoning_tokens": reasoning_tokens,
                "reasoning_effort": effort
            }
        }
    except Exception as e:
        print(f"Error: {e}")
        raise

if __name__ == "__main__":
    # Call o1 model with high reasoning effort
    print("Calling o1 model for integral problem...")
    o1_result = call_o1_model()
    print(f"Response from o1:")
    print(o1_result["content"])
    print(f"\nToken usage - Total: {o1_result['usage']['total_tokens']}, Reasoning: {o1_result['usage']['reasoning_tokens']}")
    
    print("\n" + "="*50 + "\n")
    
    # Call o3-mini model with medium reasoning effort
    print("Calling o3-mini model for code refactoring...")
    o3_mini_result = call_o3_mini_model()
    print(f"Response from o3-mini:")
    print(o3_mini_result["content"])
    print(f"\nToken usage - Total: {o3_mini_result['usage']['total_tokens']}, Reasoning: {o3_mini_result['usage']['reasoning_tokens']}")
    
    print("\n" + "="*50 + "\n")
    
    # Demonstrate different reasoning efforts
    print("Comparing different reasoning efforts on o1 model...")
    
    # Low reasoning effort
    quadratic_problem = "Solve the quadratic equation: 2x^2 - 7x + 3 = 0"
    low_effort_result = call_o1_model_with_effort(quadratic_problem, "low")
    
    # High reasoning effort
    complex_problem = "Find all values of x that satisfy the equation: sin(x) + cos(x) = 1"
    high_effort_result = call_o1_model_with_effort(complex_problem, "high")
    
    # Print comparison
    print(f"Low effort (Quadratic equation) - Reasoning tokens: {low_effort_result['usage']['reasoning_tokens']}")
    print(f"High effort (Trigonometric equation) - Reasoning tokens: {high_effort_result['usage']['reasoning_tokens']}")
    
    # You can view the traces in your HoneyHive dashboard
    print("\nView the traces in your HoneyHive dashboard!") 