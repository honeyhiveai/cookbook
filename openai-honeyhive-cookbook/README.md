# OpenAI HoneyHive Tracing Cookbook

This cookbook demonstrates how to use HoneyHive to trace OpenAI API calls across different features including chat completions, function calling, structured outputs, and reasoning models.

## Overview

HoneyHive provides observability for AI applications, allowing you to trace and monitor your OpenAI API calls. This cookbook includes examples for:

- Basic Chat Completions
- Function Calling
- Structured Outputs
- Reasoning Models (o1, o3-mini)

## Getting Started

### Prerequisites

- Python 3.11+
- An OpenAI API key
- A HoneyHive API key

### Installation

```bash
git clone https://github.com/honeyhiveai/cookbook.git
cd cookbook/openai-honeyhive-cookbook
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

### Configuration

Create a `.env` file:

```bash
HH_API_KEY=your-honeyhive-api-key
HH_PROJECT=OpenAI-traces
OPENAI_API_KEY=your-openai-api-key
```

The examples use `OpenAIInstrumentor` from OpenInference to automatically trace all OpenAI API calls:

```python
import os
from honeyhive import HoneyHiveTracer
from openinference.instrumentation.openai import OpenAIInstrumentor

tracer = HoneyHiveTracer.init(
    api_key=os.getenv("HH_API_KEY"),
    project=os.getenv("HH_PROJECT"),
)
OpenAIInstrumentor().instrument(tracer_provider=tracer.provider)
```

## Examples

1. `basic_chat.py` - Tracing basic chat completions
2. `function_calling.py` - Tracing function calling with OpenAI
3. `structured_output.py` - Tracing structured outputs (JSON responses)
4. `reasoning_models.py` - Tracing reasoning models (o1, o3-mini)
5. `multi_turn_conversation.py` - Tracing multi-turn conversations

Each example shows how HoneyHive automatically traces OpenAI API calls via the `OpenAIInstrumentor` and how you can enhance traces with `@trace` decorators on business logic.

## Viewing Traces

After running any of the examples, you can view the traces in your HoneyHive dashboard. The traces include:

- Request and response payloads
- Latency metrics
- Token usage
- Custom attributes
- Errors and exceptions

## Additional Resources

- [HoneyHive Documentation](https://docs.honeyhive.ai/)
- [OpenAI API Documentation](https://platform.openai.com/docs/api-reference)
- [OpenInference OpenAI Instrumentor](https://github.com/Arize-ai/openinference/tree/main/python/instrumentation/openinference-instrumentation-openai)
