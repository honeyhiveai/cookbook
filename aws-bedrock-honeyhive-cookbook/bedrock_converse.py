#!/usr/bin/env python3
"""
Use the Conversation API (Converse) to send a text message to Amazon Titan Text model
with HoneyHive tracing.
"""
import boto3
import os
from dotenv import load_dotenv
from honeyhive import HoneyHiveTracer, trace

# Load environment variables
load_dotenv()

# Initialize HoneyHive tracer
HoneyHiveTracer.init(
    api_key=os.getenv("HONEYHIVE_API_KEY"),
    project="aws-bedrock-examples",
    source="dev",
    session_name="bedrock-converse-api"
)

@trace
def converse_with_bedrock_model(model_id, user_message, max_tokens=512, temperature=0.5, top_p=0.9):
    """
    Converse with a Bedrock model using the Converse API.
    This function is traced by HoneyHive.
    
    :param model_id: The Bedrock model ID
    :param user_message: The message from the user
    :param max_tokens: Maximum number of tokens to generate
    :param temperature: Temperature for sampling
    :param top_p: Top-p sampling parameter
    :return: The model's response
    """
    # Create an Amazon Bedrock Runtime client
    bedrock_runtime = boto3.client(
        "bedrock-runtime", 
        region_name=os.getenv("AWS_REGION", "us-east-1")
    )
    
    # Build the conversation
    conversation = [
        {
            "role": "user",
            "content": [{"text": user_message}],
        }
    ]
    
    try:
        # Send the message to the model, using the specified inference configuration
        response = bedrock_runtime.converse(
            modelId=model_id,
            messages=conversation,
            inferenceConfig={
                "maxTokens": max_tokens, 
                "temperature": temperature, 
                "topP": top_p
            },
        )
        
        # Extract the response text
        response_text = response["output"]["message"]["content"][0]["text"]
        
        return response_text
        
    except Exception as e:
        print(f"ERROR: Can't invoke '{model_id}' with Converse API. Reason: {e}")
        raise

@trace
def multi_turn_conversation(model_id):
    """
    Demonstrate a multi-turn conversation with the model.
    This function is traced by HoneyHive.
    
    :param model_id: The Bedrock model ID
    """
    # Create an Amazon Bedrock Runtime client
    bedrock_runtime = boto3.client(
        "bedrock-runtime", 
        region_name=os.getenv("AWS_REGION", "us-east-1")
    )
    
    # Start with an empty conversation
    conversation = []
    
    try:
        # First turn
        user_message = "What are three key benefits of cloud computing?"
        print(f"\nUser: {user_message}")
        
        # Add the user message to the conversation
        conversation.append({
            "role": "user",
            "content": [{"text": user_message}],
        })
        
        # Get the model's response
        response = bedrock_runtime.converse(
            modelId=model_id,
            messages=conversation,
            inferenceConfig={"maxTokens": 512, "temperature": 0.7},
        )
        
        # Extract and print the response
        assistant_message = response["output"]["message"]["content"][0]["text"]
        print(f"Assistant: {assistant_message}")
        
        # Add the assistant's response to the conversation
        conversation.append({
            "role": "assistant",
            "content": [{"text": assistant_message}],
        })
        
        # Second turn
        user_message = "Can you elaborate on scalability?"
        print(f"\nUser: {user_message}")
        
        # Add the second user message to the conversation
        conversation.append({
            "role": "user",
            "content": [{"text": user_message}],
        })
        
        # Get the model's response
        response = bedrock_runtime.converse(
            modelId=model_id,
            messages=conversation,
            inferenceConfig={"maxTokens": 512, "temperature": 0.7},
        )
        
        # Extract and print the response
        assistant_message = response["output"]["message"]["content"][0]["text"]
        print(f"Assistant: {assistant_message}")
        
        return conversation
        
    except Exception as e:
        print(f"ERROR: Multi-turn conversation failed. Reason: {e}")
        raise

@trace
def main():
    """
    Main function to demonstrate Bedrock Converse API with HoneyHive tracing.
    """
    # Set the model ID, e.g., Amazon Titan Text G1 - Express
    model_id = "amazon.titan-text-express-v1"
    
    # Single turn conversation
    user_message = "Describe the purpose of a 'hello world' program in one line."
    print("\n=== Single Turn Conversation ===")
    print(f"User: {user_message}")
    
    response_text = converse_with_bedrock_model(model_id, user_message)
    print(f"Assistant: {response_text}")
    
    # Multi-turn conversation
    print("\n\n=== Multi-Turn Conversation ===")
    multi_turn_conversation(model_id)

if __name__ == "__main__":
    main()
