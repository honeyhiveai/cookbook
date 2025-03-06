"""
Claims Summarizer Evaluation Script
==================================

This script demonstrates how to evaluate an insurance claims summarization app
using HoneyHive's evaluation framework.

The script:
1. Sets up a claims summarizer that uses AWS Bedrock
2. Defines an evaluation function that processes inputs from a HoneyHive dataset
3. Runs the evaluation experiment against a dataset in HoneyHive

Requirements:
------------
- Python 3.8+
- boto3
- honeyhive
- Valid AWS credentials with Bedrock access
- HoneyHive API key
- A dataset in the HoneyHive platform

Usage:
------
1. Set your AWS credentials as environment variables
2. Set your HoneyHive API key as an environment variable
3. Update the dataset_id with your HoneyHive dataset ID
4. Run the script
"""

import boto3
import json
import os
from honeyhive import evaluate, enrich_span, trace


class ClaimSummarizer:
    """
    A class to summarize insurance claim logs using AWS Bedrock LLMs.
    
    This class handles the interaction with AWS Bedrock, prompt formatting,
    and integration with HoneyHive for model evaluation.
    """
    
    def __init__(self, model_id="meta.llama3-70b-instruct-v1:0", region=None):
        """
        Initialize the ClaimSummarizer with AWS Bedrock client.
        
        Args:
            model_id (str): The Bedrock model ID to use for summarization
            region (str): AWS region where Bedrock is available (defaults to AWS_REGION env var or us-west-2)
        """
        # Initialize Bedrock client with credentials from environment
        self.bedrock_runtime = boto3.client(
            service_name="bedrock-runtime",
            region_name=region or os.environ.get("AWS_REGION", "us-west-2")
        )
        self.model_id = model_id
    
    @trace()
    def generate_summary(self, log_content, max_sentences=8, ground_truth=None):
        """
        Generate a summary of claim log notes and track with HoneyHive
        
        Args:
            log_content (str): The content of the claim log as a string
            max_sentences (int): Maximum number of sentences in the summary
            ground_truth (dict, optional): Ground truth data for evaluation
            
        Returns:
            str: A summary of the claim history and next steps
        """
        # Validate inputs
        if log_content is None:
            return "No log content provided to summarize."
            
        # Ensure log_content is a string
        log_content = str(log_content)
        
        # Define prompt template with focus areas
        prompt_template = """
        Please provide a highly concise summary of the following insurance claim log notes in {{max_sentences}} sentences or fewer.
        Focus on:
        1. The nature of the claim
        2. Current status
        3. Important actions taken
        4. Next steps required
        
        LOG NOTES:
        {{log_notes}}
        
        SUMMARY:
        """
        
        # Create actual prompt by formatting the template
        prompt = prompt_template.replace("{{max_sentences}}", str(max_sentences)).replace("{{log_notes}}", log_content)
        
        # Create the request body for Bedrock with appropriate hyperparameters
        request_body = {
            "prompt": prompt,
            "max_gen_len": 512,
            "temperature": 0.1,  # Low temperature for deterministic outputs
            "top_p": 0.9,        # High top_p for focused responses
        }
        
        # Extract hyperparams from request_body
        hyperparams = {k: v for k, v in request_body.items() if k != "prompt"}
        
        # Create template in OpenAI format with placeholders for HoneyHive tracking
        template = [
            {
                "role": "user",
                "content": prompt_template
            }
        ]
        
        # Invoke the model
        response = self.bedrock_runtime.invoke_model(
            modelId=self.model_id,
            body=json.dumps(request_body)
        )
        
        # Parse the response
        response_body = json.loads(response.get("body").read())
        summary = response_body.get("generation", "")
        
        # Clean up the summary if needed
        summary = summary.strip()
        
        # Prepare feedback if ground truth is available
        feedback = {}
        if ground_truth and "result" in ground_truth:
            feedback["ground_truth"] = ground_truth["result"]
        
        # Single enrich_span call with all information for HoneyHive
        enrich_span(
            config={
                "model": self.model_id,
                "template": template,
                "hyperparameters": hyperparams
            },
            metrics={
                "summary_length": len(summary.split('.')),
                "word_count": len(summary.split())
            },
            feedback=feedback
        )
        
        return summary


def summarize_claim(inputs, ground_truths=None):
    """
    Function to be used with HoneyHive's evaluate framework.
    
    Args:
        inputs (dict): Input data from HoneyHive dataset
        ground_truths (dict, optional): Ground truth data from HoneyHive dataset
        
    Returns:
        str: The generated summary
    """
    # Extract inputs from the _params_ dictionary
    params = inputs.get("_params_", {})
    log_content = params.get("log_content")
    max_sentences = params.get("max_sentences", 6)
    
    # Initialize the summarizer
    summarizer = ClaimSummarizer()
    
    # Generate summary, passing ground_truth to the function
    summary = summarizer.generate_summary(
        log_content=log_content, 
        max_sentences=max_sentences,
        ground_truth=ground_truths
    )
    
    return summary


def main():
    """
    Main function to run the evaluation experiment
    
    This sets up and runs a HoneyHive evaluation experiment against
    a dataset of claim logs.
    """
    # Get API key from environment variables (recommended approach)
    hh_api_key = os.environ.get("HONEYHIVE_API_KEY")
    
    # If not set in environment, you can set it here (not recommended for production)
    if not hh_api_key:
        hh_api_key = "your_honeyhive_api_key"  # Replace with your actual API key
    
    # Run the experiment
    evaluate(
        function=summarize_claim,
        hh_api_key=hh_api_key,
        hh_project="Insurance Claims Summarization",
        name="Claims Summarizer Evaluation",
        
        # IMPORTANT: Replace with your dataset ID from the HoneyHive console
        dataset_id="your_dataset_id_here",
        
        # Add any evaluators you want to use - these should be function references
        evaluators=[
            # Example evaluators - uncomment and customize as needed
            # accuracy_evaluator,     # Custom function you've defined above
            # relevance_evaluator,    # Another custom evaluation function
            # lambda x, y: some_evaluation_logic(x, y)  # Or inline lambda functions
        ],
        
        # Uncomment for enterprise deployments with dedicated servers
        # server_url='https://[org_name].api.honeyhive.ai'
    )


if __name__ == "__main__":
    main()