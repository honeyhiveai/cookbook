# Azure OpenAI HoneyHive Tracing Cookbook

This cookbook demonstrates how to use HoneyHive to trace Azure OpenAI API calls across different features including chat completions, function calling, structured outputs, and reasoning models.

## Overview

HoneyHive provides observability for AI applications. Azure OpenAI uses the same `openai` Python package as standard OpenAI, so the same `OpenAIInstrumentor` works for both.

This cookbook includes examples for:

- Basic Chat Completions
- Function Calling
- Structured Outputs
- Reasoning Models
- Multi-Turn Conversations

## Getting Started

### Prerequisites

- Python 3.11+
- An Azure OpenAI resource with deployed models
- A HoneyHive API key

### Installation

```bash
git clone https://github.com/honeyhiveai/cookbook.git
cd cookbook/azure-openai-honeyhive-cookbook
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

### Configuration

Create a `.env` file:

```bash
HH_API_KEY=your-honeyhive-api-key
HH_PROJECT=Azure-OpenAI-traces
AZURE_OPENAI_API_KEY=your-azure-openai-key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
```

The examples use `OpenAIInstrumentor` to automatically trace all Azure OpenAI API calls:

```python
import os
from honeyhive import HoneyHiveTracer
from openinference.instrumentation.openai import OpenAIInstrumentor
from openai import AzureOpenAI

tracer = HoneyHiveTracer.init(
    api_key=os.getenv("HH_API_KEY"),
    project=os.getenv("HH_PROJECT"),
)
OpenAIInstrumentor().instrument(tracer_provider=tracer.provider)

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version="2024-10-21",
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
)
```

## Examples

1. `basic_chat.py` - Tracing basic chat completions
2. `function_calling.py` - Tracing function calling with Azure OpenAI
3. `structured_output.py` - Tracing structured outputs (JSON responses)
4. `reasoning_models.py` - Tracing reasoning models
5. `multi_turn_conversation.py` - Tracing multi-turn conversations

## Additional Resources

- [HoneyHive Documentation](https://docs.honeyhive.ai/)
- [Azure OpenAI Documentation](https://learn.microsoft.com/en-us/azure/ai-services/openai/)
- [OpenInference OpenAI Instrumentor](https://github.com/Arize-ai/openinference/tree/main/python/instrumentation/openinference-instrumentation-openai)
