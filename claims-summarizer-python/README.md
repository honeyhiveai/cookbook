# Insurance Claims Summarizer with AWS Bedrock and HoneyHive

This cookbook demonstrates an automated insurance claims summarization system using AWS Bedrock LLMs and HoneyHive for observability and evaluation. The system processes insurance claim log notes and generates concise summaries.

## Overview

- `log_notes_trace.py` - Tracing demo: summarizes a sample claim with HoneyHive tracing
- `log_notes_eval.py` - Evaluation: runs batch evaluation against a HoneyHive dataset
- `log_notes.jsonl` - Sample insurance claim log data

## Setup

### Prerequisites

- Python 3.11+
- AWS account with Bedrock access
- HoneyHive API key

### Installation

```bash
git clone https://github.com/honeyhiveai/cookbook.git
cd cookbook/claims-summarizer-python
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

### Configuration

Create a `.env` file:

```bash
HH_API_KEY=your-honeyhive-api-key
HH_PROJECT=Insurance Claims Summarization
AWS_ACCESS_KEY_ID=your-aws-access-key
AWS_SECRET_ACCESS_KEY=your-aws-secret-key
AWS_DEFAULT_REGION=us-west-2
```

### Tracing setup

The tracing script uses `BedrockInstrumentor` for automatic Bedrock call tracing:

```python
import os
from honeyhive import HoneyHiveTracer, trace
from openinference.instrumentation.bedrock import BedrockInstrumentor

tracer = HoneyHiveTracer.init(
    api_key=os.getenv("HH_API_KEY"),
    project=os.getenv("HH_PROJECT"),
)
BedrockInstrumentor().instrument(tracer_provider=tracer.provider)
```

## Usage

### Run Tracing Demo

```bash
uv run python log_notes_trace.py
```

### Run Evaluation

1. Upload `log_notes.jsonl` to HoneyHive as a dataset
2. Copy the dataset ID and update it in `log_notes_eval.py`
3. Run:

```bash
uv run python log_notes_eval.py
```

## Model Customization

The scripts use Meta Llama 3 70B via Bedrock by default. Change the model:

```python
summarizer = ClaimSummarizer(model_id="anthropic.claude-3-sonnet-20240229-v1:0")
```

## References

- [HoneyHive Documentation](https://docs.honeyhive.ai/)
- [AWS Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)
