#!/usr/bin/env python3
"""
Use the native inference API to send a text message to Amazon Titan Text model
with HoneyHive tracing.
"""
import boto3
import json
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
    session_name="invoke-bedrock-model"
)

@trace
def invoke_bedrock_model(model_id, prompt, max_tokens=512, temperature=0.5, top_p=0.9):
    """
    Invoke a Bedrock model using InvokeModel API.
    This function is traced by HoneyHive.
    
    :param model_id: The Bedrock model ID
    :param prompt: The prompt text
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
    
    # Format the request payload using the model's native structure
    native_request = {
        "inputText": prompt,
        "textGenerationConfig": {
            "maxTokenCount": max_tokens,
            "temperature": temperature,
            "topP": top_p
        },
    }
    
    # Convert the native request to JSON
    request = json.dumps(native_request)
    
    try:
        # Invoke the model with the request
        response = bedrock_runtime.invoke_model(modelId=model_id, body=request)
        
        # Decode the response body
        model_response = json.loads(response["body"].read())
        
        # Extract the response text
        response_text = model_response["results"][0]["outputText"]
        
        return response_text
    
    except Exception as e:
        print(f"ERROR: Can't invoke '{model_id}'. Reason: {e}")
        raise

@trace
def main():
    """
    Main function to demonstrate Bedrock model invocation with HoneyHive tracing.
    """
    # Set the model ID, e.g., Amazon Titan Text G1 - Express
    model_id = "amazon.titan-text-express-v1"
    
    # Define the prompt for the model
    prompt = "Describe the purpose of a 'hello world' program in one line."
    
    # Invoke the model
    response_text = invoke_bedrock_model(model_id, prompt)
    
    # Print the response
    print("\nBedrock Model Response:")
    print("-----------------------")
    print(response_text)
    print("-----------------------")

if __name__ == "__main__":
    main()
