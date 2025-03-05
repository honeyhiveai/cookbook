"""
Claims Summarizer with AWS Bedrock and HoneyHive Tracing
========================================================

This script demonstrates how to create a claims summarization service using:
- AWS Bedrock for LLM inference
- HoneyHive for tracking and observability
- Boto3 for AWS API interactions

The script reads insurance claim logs and generates concise summaries focused on:
1. The nature of the claim
2. Current status 
3. Important actions taken
4. Next steps required

Requirements:
-------------
- Python 3.8+
- boto3
- honeyhive
- Valid AWS credentials with Bedrock access
- HoneyHive API key

"""

import boto3
import json
import os
from honeyhive.tracer import HoneyHiveTracer
from honeyhive.tracer.custom import trace, enrich_span


class ClaimSummarizer:
    """
    A class to summarize insurance claim logs using AWS Bedrock LLMs.
    
    This class handles the interaction with AWS Bedrock, prompt formatting,
    and integration with HoneyHive for model observability.
    """
    
    def __init__(self, model_id="meta.llama3-70b-instruct-v1:0", region="us-west-2"):
        """
        Initialize the ClaimSummarizer with AWS Bedrock client.
        
        Args:
            model_id (str): The Bedrock model ID to use for summarization
            region (str): AWS region where Bedrock is available
        """
        # Initialize Bedrock client with credentials from environment
        self.bedrock_runtime = boto3.client(
            service_name="bedrock-runtime",
            region_name=region
        )
        self.model_id = model_id
    
    @trace()
    def generate_summary(self, log_content, max_sentences=8):
        """
        Generate a summary of claim log notes
        
        Args:
            log_content (str): The content of the claim log as a string
            max_sentences (int): Maximum number of sentences in the summary (4-8)
            
        Returns:
            str: A summary of the claim history and next steps
        """
        # Define prompt template for the summarization task
        prompt_template = """
        Please provide a concise summary of the following insurance claim log notes in {{max_sentences}} sentences or fewer.
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
        
        # Create the request body for Bedrock with hyperparameters
        request_body = {
            "prompt": prompt,
            "max_gen_len": 512,
            "temperature": 0.1,  # Low temperature for more deterministic output
            "top_p": 0.9,        # High top_p for focused but slightly diverse responses
        }
        
        # Extract hyperparams from request_body to ensure they match exactly
        hyperparams = {k: v for k, v in request_body.items() if k != "prompt"}
        
        # Create template in OpenAI format with placeholders for HoneyHive tracking
        openai_format_template = [
            {
                "role": "user",
                "content": """
        Please provide a concise summary of the following insurance claim log notes in {{max_sentences}} sentences or fewer.
        Focus on:
        1. The nature of the claim
        2. Current status
        3. Important actions taken
        4. Next steps required
        
        LOG NOTES:
        {{log_notes}}
        
        SUMMARY:
        """
            }
        ]
        
        # Invoke the Bedrock model
        response = self.bedrock_runtime.invoke_model(
            modelId=self.model_id,
            body=json.dumps(request_body)
        )
        
        # Parse the response
        response_body = json.loads(response.get("body").read())
        summary = response_body.get("generation", "")
        
        # Clean up the summary if needed
        summary = summary.strip()
        
        # Add HoneyHive enrich_span with config and metric tracking
        enrich_span(
            config={
                "model": self.model_id,
                "template": openai_format_template,
                "hyperparameters": hyperparams
            },
            metrics={
                "summary_length": len(summary.split('.')),  # Count sentences
                "word_count": len(summary.split())          # Count words
            }
        )
        
        return summary


def init_honeyhive():
    """
    Initialize HoneyHive for model observability.
    
    This function sets up the HoneyHive tracer with the appropriate
    project information and API key.
    """
    # Initialize HoneyHive with your API key (use environment variables in production)
    HoneyHiveTracer.init(
        api_key=os.environ.get("HONEYHIVE_API_KEY", "your_api_key_here"),
        project="Insurance Claims Summarization",
        source="development",
        session_name="Claims Summarizer",
        # For enterprise deployments, uncomment and use your org's server URL:
        # server_url='https://[org_name].api.honeyhive.ai' 
    )


def main():
    """
    Main function to demonstrate the claim summarizer
    
    This function shows how to:
    1. Set up AWS credentials (use env vars or AWS credentials provider in production)
    2. Initialize the summarizer
    3. Process sample claim data
    4. Display the generated summary
    """
    # IMPORTANT: In production, use environment variables, AWS IAM roles, 
    # or a credentials provider instead of hardcoded credentials
    # os.environ["AWS_ACCESS_KEY_ID"] = "YOUR_ACCESS_KEY"      # Replace with your access key
    # os.environ["AWS_SECRET_ACCESS_KEY"] = "YOUR_SECRET_KEY"  # Replace with your secret key
    
    # Initialize HoneyHive
    init_honeyhive()
    
    # Initialize the summarizer
    summarizer = ClaimSummarizer()
    
    # Example claim ID
    claim_id = "CL-12345"
    
    # Sample log content as a single string
    # In a real application, this would be fetched from a database or API
    sample_log = """2023-12-01 09:23:45 [John Smith] Initial claim filed. Customer reported water damage to kitchen from leaking pipe. Estimated damage $5,000.

2023-12-02 14:10:22 [Sarah Johnson] Assigned inspector Mike Brown to visit property on 12/05. Customer notified of appointment.

2023-12-05 16:45:33 [Mike Brown] Completed on-site inspection. Confirmed water damage from pipe under sink. Took measurements and photos. Damage extends to flooring and lower cabinets. Estimated repair costs $7,200.

2023-12-06 10:15:00 [Sarah Johnson] Reviewed inspection report. Claim approved for $7,200. Awaiting customer's selection of contractor from approved list.

2023-12-10 11:30:15 [John Smith] Customer selected ABC Restoration for repairs. Work scheduled to begin 12/15.

2023-12-20 15:45:22 [John Smith] Received progress update from contractor. Cabinets removed, new flooring being installed. Expected completion 12/28."""
    
    # Generate and print the summary
    print(f"Generating summary for claim {claim_id}...")
    summary = summarizer.generate_summary(sample_log, max_sentences=6)
    
    print("\nSummary:")
    print("=" * 80)
    print(summary)
    print("=" * 80)


if __name__ == "__main__":
    main()