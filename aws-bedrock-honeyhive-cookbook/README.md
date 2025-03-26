# AWS Bedrock + HoneyHive Tracing Cookbook

This cookbook demonstrates how to implement tracing for AWS Bedrock models using HoneyHive.

## Overview

This cookbook includes:
- Basic AWS Bedrock integration examples
- HoneyHive tracing implementation
- Examples for different Bedrock models and operations

## Setup

1. Install the required dependencies:
```
pip install -r requirements.txt
```

2. Set up your AWS credentials:
```
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_REGION=your_region
```

3. Set up your HoneyHive API key:
```
export HONEYHIVE_API_KEY=your_api_key
```

## Examples

- `bedrock_list_models.py`: Lists available Bedrock models with HoneyHive tracing
- `bedrock_invoke_model.py`: Basic text generation using InvokeModel with tracing
- `bedrock_converse.py`: Text generation using the Converse API with tracing
- `bedrock_advanced.py`: More advanced usage examples with custom span tracing

## References

- [HoneyHive Documentation](https://docs.honeyhive.ai/)
- [AWS Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)
