"""
Claims Summarizer Evaluation Script

Evaluates an insurance claims summarization app using HoneyHive's
evaluation framework with AWS Bedrock.
"""

import json
import os

import boto3
from dotenv import load_dotenv

from honeyhive import evaluate, trace

load_dotenv(override=True)

# Initialize AWS Bedrock client
bedrock = boto3.client(
    service_name="bedrock-runtime",
    region_name=os.getenv("AWS_REGION", "us-west-2"),
)

MODEL_ID = "meta.llama3-70b-instruct-v1:0"

PROMPT_TEMPLATE = """Please provide a highly concise summary of the following insurance claim log notes in {max_sentences} sentences or fewer.
Focus on:
1. The nature of the claim
2. Current status
3. Important actions taken
4. Next steps required

LOG NOTES:
{log_notes}

SUMMARY:"""


@trace()
def generate_summary(log_content: str, max_sentences: int = 6) -> str:
    """Generate a summary of claim log notes using Bedrock."""
    if not log_content:
        return "No log content provided to summarize."

    prompt = PROMPT_TEMPLATE.format(max_sentences=max_sentences, log_notes=str(log_content))

    response = bedrock.invoke_model(
        modelId=MODEL_ID,
        body=json.dumps({
            "prompt": prompt,
            "max_gen_len": 512,
            "temperature": 0.1,
            "top_p": 0.9,
        }),
    )

    result = json.loads(response["body"].read())
    return result.get("generation", "").strip()


def summarize_claim(inputs, ground_truths=None):
    """Evaluation function for HoneyHive's evaluate framework."""
    params = inputs.get("_params_", {})
    return generate_summary(
        log_content=params.get("log_content"),
        max_sentences=params.get("max_sentences", 6),
    )


if __name__ == "__main__":
    evaluate(
        function=summarize_claim,
        hh_api_key=os.getenv("HH_API_KEY"),
        hh_project=os.getenv("HH_PROJECT", "Insurance Claims Summarization"),
        name="Claims Summarizer Evaluation",
        dataset_id="your_dataset_id_here",  # Replace with your HoneyHive dataset ID
        evaluators=[],
    )
