"""
Claims Summarizer with AWS Bedrock and HoneyHive Tracing

Reads insurance claim logs and generates concise summaries using
AWS Bedrock, with HoneyHive observability.
"""

import json
import os

import boto3
from dotenv import load_dotenv

from honeyhive import HoneyHiveTracer, trace
from openinference.instrumentation.bedrock import BedrockInstrumentor

load_dotenv(override=True)

# Initialize HoneyHive tracer and Bedrock auto-instrumentation
tracer = HoneyHiveTracer.init(
    api_key=os.getenv("HH_API_KEY"),
    project=os.getenv("HH_PROJECT", "Insurance Claims Summarization"),
    source="development",
    session_name="Claims Summarizer",
)
BedrockInstrumentor().instrument(tracer_provider=tracer.provider)

# Initialize AWS Bedrock client
bedrock = boto3.client(
    service_name="bedrock-runtime",
    region_name=os.getenv("AWS_REGION", "us-west-2"),
)

MODEL_ID = "meta.llama3-70b-instruct-v1:0"

PROMPT_TEMPLATE = """Please provide a concise summary of the following insurance claim log notes in {max_sentences} sentences or fewer.
Focus on:
1. The nature of the claim
2. Current status
3. Important actions taken
4. Next steps required

LOG NOTES:
{log_notes}

SUMMARY:"""


@trace()
def summarize_claim(log_content: str, max_sentences: int = 6) -> str:
    """Generate a summary of claim log notes using Bedrock."""
    prompt = PROMPT_TEMPLATE.format(max_sentences=max_sentences, log_notes=log_content)

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


# Sample claim data
SAMPLE_LOG = """2023-12-01 09:23:45 [John Smith] Initial claim filed. Customer reported water damage to kitchen from leaking pipe. Estimated damage $5,000.

2023-12-02 14:10:22 [Sarah Johnson] Assigned inspector Mike Brown to visit property on 12/05. Customer notified of appointment.

2023-12-05 16:45:33 [Mike Brown] Completed on-site inspection. Confirmed water damage from pipe under sink. Took measurements and photos. Damage extends to flooring and lower cabinets. Estimated repair costs $7,200.

2023-12-06 10:15:00 [Sarah Johnson] Reviewed inspection report. Claim approved for $7,200. Awaiting customer's selection of contractor from approved list.

2023-12-10 11:30:15 [John Smith] Customer selected ABC Restoration for repairs. Work scheduled to begin 12/15.

2023-12-20 15:45:22 [John Smith] Received progress update from contractor. Cabinets removed, new flooring being installed. Expected completion 12/28."""

if __name__ == "__main__":
    claim_id = "CL-12345"
    print(f"Generating summary for claim {claim_id}...")

    summary = summarize_claim(SAMPLE_LOG)
    print(f"\nSummary:\n{'=' * 60}\n{summary}\n{'=' * 60}")
