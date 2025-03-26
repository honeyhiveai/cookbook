#!/usr/bin/env python3
"""
Lists the available Amazon Bedrock models with HoneyHive tracing.
"""
import logging
import json
import boto3
import os
from dotenv import load_dotenv
from honeyhive import HoneyHiveTracer, trace

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize HoneyHive tracer
HoneyHiveTracer.init(
    api_key=os.getenv("HONEYHIVE_API_KEY"),
    project="aws-bedrock-examples",
    source="dev",
    session_name="list-bedrock-models"
)

@trace
def list_foundation_models(bedrock_client):
    """
    Gets a list of available Amazon Bedrock foundation models.
    This function is traced by HoneyHive.

    :return: The list of available bedrock foundation models.
    """
    try:
        response = bedrock_client.list_foundation_models()
        models = response["modelSummaries"]
        logger.info("Got %s foundation models.", len(models))
        return models
    except Exception as e:
        logger.error("Couldn't list foundation models: %s", str(e))
        raise

@trace
def main():
    """
    Entry point for the example. Uses the AWS SDK for Python (Boto3)
    to create an Amazon Bedrock client. Then lists the available Bedrock models
    in the region set in the caller's profile and credentials.
    """
    # Create Bedrock client
    bedrock_client = boto3.client(
        service_name="bedrock",
        region_name=os.getenv("AWS_REGION", "us-east-1")
    )

    # Get and display models
    fm_models = list_foundation_models(bedrock_client)
    for model in fm_models:
        print(f"Model: {model['modelName']}")
        print(json.dumps(model, indent=2))
        print("---------------------------\n")

    logger.info("Done.")

if __name__ == "__main__":
    main()
