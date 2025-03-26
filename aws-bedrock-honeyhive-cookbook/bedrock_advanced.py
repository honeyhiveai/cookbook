#!/usr/bin/env python3
"""
Advanced usage examples for AWS Bedrock with HoneyHive tracing.
This example demonstrates:
1. Custom span tracing for workflow components
2. Adding custom metrics to traces
3. Tracing for more complex operations
"""
import boto3
import json
import os
import time
import uuid
from dotenv import load_dotenv
from honeyhive import HoneyHiveTracer, trace

# Load environment variables
load_dotenv()

# Initialize HoneyHive tracer
HoneyHiveTracer.init(
    api_key=os.getenv("HONEYHIVE_API_KEY"),
    project="aws-bedrock-examples",
    source="dev",
    session_name="advanced-bedrock-tracing"
)

@trace
def get_bedrock_model_info(bedrock_client, model_id):
    """
    Get detailed information about a specific Bedrock model.
    This function is traced by HoneyHive.
    
    :param bedrock_client: Boto3 Bedrock client
    :param model_id: The model ID to query
    :return: Model information
    """
    try:
        # Get list of all models
        response = bedrock_client.list_foundation_models()
        models = response["modelSummaries"]
        
        # Find the specific model
        for model in models:
            if model["modelId"] == model_id:
                return model
                
        return None
    except Exception as e:
        print(f"Error getting model info: {str(e)}")
        raise

@trace
def generate_article_outline(bedrock_runtime, model_id, topic):
    """
    Generate an article outline using Bedrock.
    This function is traced by HoneyHive.
    
    :param bedrock_runtime: Boto3 Bedrock Runtime client
    :param model_id: Model ID to use
    :param topic: Article topic
    :return: Generated outline
    """
    start_time = time.time()
    
    prompt = f"Create a detailed outline for an article about {topic}. " \
             f"Include an introduction, at least 3 main sections with subsections, and a conclusion."
    
    native_request = {
        "inputText": prompt,
        "textGenerationConfig": {
            "maxTokenCount": 800,
            "temperature": 0.7,
            "topP": 0.9
        },
    }
    
    request = json.dumps(native_request)
    
    try:
        # Invoke the model
        response = bedrock_runtime.invoke_model(modelId=model_id, body=request)
        
        # Parse response
        model_response = json.loads(response["body"].read())
        outline = model_response["results"][0]["outputText"]
        
        # Calculate metrics
        end_time = time.time()
        generation_time = end_time - start_time
        
        # Add custom metrics to the HoneyHive trace
        HoneyHiveTracer.current_session().add_trace_metadata({
            "generation_time_seconds": generation_time,
            "input_length": len(prompt),
            "output_length": len(outline),
            "operation": "article_outline_generation",
            "topic": topic
        })
        
        return outline
        
    except Exception as e:
        print(f"Error generating article outline: {str(e)}")
        raise

@trace
def expand_outline_section(bedrock_runtime, model_id, outline, section_title):
    """
    Expand a specific section of the outline into paragraphs.
    This function is traced by HoneyHive.
    
    :param bedrock_runtime: Boto3 Bedrock Runtime client
    :param model_id: Model ID to use
    :param outline: The full outline
    :param section_title: Title of the section to expand
    :return: Expanded content for the section
    """
    prompt = f"Here is an outline for an article:\n\n{outline}\n\n" \
             f"Please expand the section titled '{section_title}' into 2-3 detailed paragraphs."
    
    # Build conversation for Converse API
    conversation = [
        {
            "role": "user",
            "content": [{"text": prompt}],
        }
    ]
    
    try:
        # Use Converse API
        response = bedrock_runtime.converse(
            modelId=model_id,
            messages=conversation,
            inferenceConfig={
                "maxTokens": 1000, 
                "temperature": 0.8
            },
        )
        
        # Extract response
        expanded_section = response["output"]["message"]["content"][0]["text"]
        
        return expanded_section
        
    except Exception as e:
        print(f"Error expanding section: {str(e)}")
        raise

@trace
def run_rag_example(bedrock_runtime, model_id, query, context):
    """
    Simple RAG (Retrieval-Augmented Generation) example with tracing.
    This function is traced by HoneyHive.
    
    :param bedrock_runtime: Boto3 Bedrock Runtime client
    :param model_id: Model ID to use
    :param query: User query
    :param context: Retrieved context information
    :return: Generated response
    """
    request_id = str(uuid.uuid4())
    
    # Create a prompt that includes the context
    prompt = f"Context information:\n{context}\n\nBased on the above context, answer the following question: {query}"
    
    native_request = {
        "inputText": prompt,
        "textGenerationConfig": {
            "maxTokenCount": 500,
            "temperature": 0.4,
            "topP": 0.9
        },
    }
    
    request = json.dumps(native_request)
    
    try:
        # Invoke the model
        response = bedrock_runtime.invoke_model(modelId=model_id, body=request)
        
        # Parse response
        model_response = json.loads(response["body"].read())
        answer = model_response["results"][0]["outputText"]
        
        # Add RAG-specific metrics to the trace
        HoneyHiveTracer.current_session().add_trace_metadata({
            "request_id": request_id,
            "context_length": len(context),
            "query_length": len(query),
            "answer_length": len(answer),
            "operation": "rag",
            "query": query
        })
        
        return answer
        
    except Exception as e:
        print(f"Error in RAG example: {str(e)}")
        raise

@trace
def main():
    """
    Main function demonstrating advanced Bedrock usage with HoneyHive tracing.
    """
    # Create Bedrock clients
    bedrock_client = boto3.client(
        service_name="bedrock", 
        region_name=os.getenv("AWS_REGION", "us-east-1")
    )
    
    bedrock_runtime = boto3.client(
        service_name="bedrock-runtime", 
        region_name=os.getenv("AWS_REGION", "us-east-1")
    )
    
    # Set model ID
    model_id = "amazon.titan-text-express-v1"
    
    # 1. Get model information
    print("\n=== Model Information ===")
    model_info = get_bedrock_model_info(bedrock_client, model_id)
    if model_info:
        print(f"Model Name: {model_info.get('modelName')}")
        print(f"Model ID: {model_info.get('modelId')}")
        print(f"Provider: {model_info.get('providerName')}")
    
    # 2. Generate article outline
    print("\n=== Article Outline Generation ===")
    topic = "The impact of artificial intelligence on healthcare"
    outline = generate_article_outline(bedrock_runtime, model_id, topic)
    print(f"Outline for '{topic}':")
    print(outline)
    
    # 3. Expand a section
    print("\n=== Section Expansion ===")
    section_title = "Introduction"  # Assumes this section exists in the outline
    expanded_section = expand_outline_section(bedrock_runtime, model_id, outline, section_title)
    print(f"Expanded '{section_title}' section:")
    print(expanded_section)
    
    # 4. RAG example
    print("\n=== RAG Example ===")
    query = "What are the ethical considerations of AI in healthcare?"
    # In a real application, this context would come from a retrieval system
    context = """
    Ethical considerations in AI healthcare applications include privacy concerns related to patient data, 
    potential biases in AI algorithms that could lead to healthcare disparities, questions about liability 
    when AI systems make mistakes, and the changing role of healthcare professionals as AI systems become 
    more advanced. Additionally, there are concerns about equitable access to AI healthcare technologies
    and ensuring AI systems are transparent and explainable to both healthcare providers and patients.
    """
    
    answer = run_rag_example(bedrock_runtime, model_id, query, context)
    print(f"Query: {query}")
    print(f"Answer: {answer}")

if __name__ == "__main__":
    main()
