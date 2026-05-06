# AWS Bedrock + HoneyHive Tracing Cookbook

This cookbook demonstrates how to implement tracing for AWS Bedrock models using HoneyHive.

## Overview

This cookbook includes:
- Basic AWS Bedrock integration examples
- HoneyHive tracing with `BedrockInstrumentor` for automatic model invocation tracing
- Examples for different Bedrock models and operations

## Setup

1. Install dependencies:
```bash
git clone https://github.com/honeyhiveai/cookbook.git
cd cookbook/aws-bedrock-honeyhive-cookbook
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

2. Create a `.env` file:
```bash
HH_API_KEY=your-honeyhive-api-key
HH_PROJECT=aws-bedrock-examples
AWS_ACCESS_KEY_ID=your-aws-access-key
AWS_SECRET_ACCESS_KEY=your-aws-secret-key
AWS_DEFAULT_REGION=us-east-1
```

The examples use `BedrockInstrumentor` to automatically trace all Bedrock API calls:

```python
import os
from honeyhive import HoneyHiveTracer
from openinference.instrumentation.bedrock import BedrockInstrumentor

tracer = HoneyHiveTracer.init(
    api_key=os.getenv("HH_API_KEY"),
    project=os.getenv("HH_PROJECT"),
)
BedrockInstrumentor().instrument(tracer_provider=tracer.provider)
```

## Examples

- `bedrock_list_models.py`: Lists available Bedrock models with HoneyHive tracing
- `bedrock_invoke_model.py`: Basic text generation using InvokeModel with tracing
- `bedrock_converse.py`: Text generation using the Converse API with tracing
- `bedrock_advanced.py`: Advanced usage examples with custom span tracing

## References

- [HoneyHive Documentation](https://docs.honeyhive.ai/)
- [AWS Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)
- [OpenInference Bedrock Instrumentor](https://github.com/Arize-ai/openinference/tree/main/python/instrumentation/openinference-instrumentation-bedrock)
