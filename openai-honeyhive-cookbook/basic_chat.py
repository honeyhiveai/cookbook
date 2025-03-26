"""
This example demonstrates how to trace basic OpenAI chat completions with HoneyHive.
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

# Simple function to call OpenAI chat completions API
@trace
def basic_chat_completion():
    """Make a simple chat completion call to OpenAI API."""
    try:
        # This call will be automatically traced by HoneyHive
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "What is the capital of France?"}
            ],
            temperature=0.7,
            max_tokens=150
        )
        
        # Return the response content
        return response.choices[0].message.content
    except Exception as e:
        # Errors will be captured in the trace
        print(f"Error: {e}")
        raise

# Using the custom metadata to enrich your traces
@trace
def annotated_chat_completion(question):
    """Make a chat completion call with custom annotations and metadata."""
    try:
        # This call will be automatically traced by HoneyHive
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": question}
            ],
            temperature=0.7,
            max_tokens=150
        )
        
        # Return the response content
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error: {e}")
        raise

if __name__ == "__main__":
    # Make a basic chat completion call
    answer = basic_chat_completion()
    print(f"Basic chat completion response: {answer}")
    
    # Make a chat completion call with custom annotations
    question = "What are the three largest cities in Japan?"
    answer = annotated_chat_completion(question)
    print(f"Question: {question}")
    print(f"Answer: {answer}")
    
    # You can view the traces in your HoneyHive dashboard
    print("\nView the traces in your HoneyHive dashboard!") 