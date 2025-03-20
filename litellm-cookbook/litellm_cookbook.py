"""
HoneyHive Integration with LiteLLM

This example demonstrates how to integrate HoneyHive tracing with LiteLLM
for monitoring and optimizing LLM calls in applications.
"""

import os
import litellm
from honeyhive import HoneyHiveTracer, trace

# Set your API keys
HONEYHIVE_API_KEY = "your honeyhive api key"
OPENAI_API_KEY = "your openai api key"

# Set OpenAI API key for LiteLLM
litellm.api_key = OPENAI_API_KEY

# Initialize HoneyHive tracer
HoneyHiveTracer.init(
    api_key=HONEYHIVE_API_KEY,
    project="your project name",
    source="dev",
    session_name="litellm_example"
)

@trace
def initialize_litellm():
    """Initialize LiteLLM with configuration."""
    try:
        # Set default model
        litellm.set_verbose = True
        
        # Configure model list for fallbacks (optional)
        litellm.model_list = [
            {
                "model_name": "gpt-4o-mini",
                "litellm_params": {
                    "model": "gpt-4o-mini",
                    "api_key": OPENAI_API_KEY
                }
            }
        ]
        
        print("LiteLLM initialized successfully")
    except Exception as e:
        print(f"Error initializing LiteLLM: {e}")
        raise

@trace
def generate_completion(prompt, model="gpt-4o-mini", temperature=0.7, max_tokens=500):
    """Generate a completion using LiteLLM with tracing."""
    try:
        response = litellm.completion(
            model=model,
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        completion_text = response.choices[0].message.content
        print(f"Generated completion with {len(completion_text)} characters")
        return completion_text
    except Exception as e:
        print(f"Error generating completion: {e}")
        raise

@trace
def generate_chat_completion(messages, model="gpt-3.5-turbo", temperature=0.7, max_tokens=500):
    """Generate a chat completion using LiteLLM with tracing."""
    try:
        response = litellm.completion(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        completion_text = response.choices[0].message.content
        print(f"Generated chat completion with {len(completion_text)} characters")
        return completion_text
    except Exception as e:
        print(f"Error generating chat completion: {e}")
        raise

@trace
def generate_embedding(text, model="text-embedding-ada-002"):
    """Generate embeddings using LiteLLM with tracing."""
    
    response = litellm.embedding(
            model=model,
            input=text)
        
    
    
    return print("Embedding generated")
    

@trace
def process_with_fallback(messages, primary_model="gpt-3.5-turbo", fallback_model="gpt-4"):
    """Process messages with a fallback model if the primary model fails."""
    try:
        # Try primary model first
        print(f"Attempting to use primary model: {primary_model}")
        return generate_chat_completion(messages, model=primary_model)
    except Exception as primary_error:
        print(f"Primary model failed: {primary_error}")
        try:
            # Fall back to secondary model
            print(f"Falling back to secondary model: {fallback_model}")
            return generate_chat_completion(messages, model=fallback_model)
        except Exception as fallback_error:
            print(f"Fallback model also failed: {fallback_error}")
            raise

@trace
def batch_process_prompts(prompts, model="gpt-3.5-turbo"):
    """Process multiple prompts in batch with tracing."""
    results = []
    for i, prompt in enumerate(prompts):
        try:
            print(f"Processing prompt {i+1}/{len(prompts)}")
            result = generate_completion(prompt, model=model)
            results.append({"prompt": prompt, "completion": result, "status": "success"})
        except Exception as e:
            print(f"Error processing prompt {i+1}: {e}")
            results.append({"prompt": prompt, "completion": None, "status": "error", "error": str(e)})
    
    return results

def main():
    # Initialize LiteLLM
    initialize_litellm()
    
    # Example 1: Simple completion
    prompt = "Explain the concept of vector databases in simple terms."
    completion = generate_completion(prompt)
    print("\n=== Simple Completion ===")
    print(completion)
    
    # Example 2: Chat completion
    messages = [
        {"role": "system", "content": "You are a helpful assistant that explains technical concepts clearly."},
        {"role": "user", "content": "What is HoneyHive and how does it help with AI observability?"}
    ]
    chat_completion = generate_chat_completion(messages)
    print("\n=== Chat Completion ===")
    print(chat_completion)
    
    # Example 3: Generate embedding
    text = "HoneyHive provides tracing and monitoring for AI applications."
    embedding = generate_embedding(text)
    print(f"\n=== Embedding ===")
    print(f"Generated embeddings: {embedding}")
    
    # Example 4: Process with fallback
    fallback_messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Write a short poem about AI observability."}
    ]
    fallback_result = process_with_fallback(fallback_messages)
    print("\n=== Fallback Processing ===")
    print(fallback_result)
    
    # Example 5: Batch processing
    batch_prompts = [
        "What are vector databases?",
        "Explain the concept of RAG in AI applications.",
        "How does tracing help improve AI applications?"
    ]
    batch_results = batch_process_prompts(batch_prompts)
    print("\n=== Batch Processing Results ===")
    for i, result in enumerate(batch_results):
        print(f"Prompt {i+1} Status: {result['status']}")

if __name__ == "__main__":
    main()
