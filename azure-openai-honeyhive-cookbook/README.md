# Azure OpenAI HoneyHive Tracing Cookbook

This cookbook demonstrates how to use HoneyHive to trace Azure OpenAI API calls across different features including chat completions, function calling, structured outputs, and reasoning models.

## Overview

HoneyHive provides observability for AI applications, allowing you to trace and monitor your Azure OpenAI API calls. This cookbook includes examples for:

- Basic Chat Completions
- Function Calling
- Structured Outputs
- Multi-turn Conversations
- Reasoning Models (where supported by Azure OpenAI)

## Getting Started

### Prerequisites

- Python 3.8+
- An Azure OpenAI resource with API access
- A HoneyHive API key

### Installation

```bash
pip install openai honeyhive
```

### Configuration

Set your API keys and Azure configuration as environment variables or directly in the code (for demonstration purposes only):

```python
import os
from openai import AzureOpenAI
from honeyhive import HoneyHiveTracer

# Initialize HoneyHive tracer
HoneyHiveTracer.init(
    api_key="your_honeyhive_api_key",
    project="Azure-OpenAI-traces"
)

# Initialize Azure OpenAI client
client = AzureOpenAI(
    api_version="2023-07-01-preview",
    azure_endpoint="https://your-endpoint.openai.azure.com",
)
```

## Examples

This cookbook contains the following examples:

1. `basic_chat.py` - Tracing basic chat completions
2. `function_calling.py` - Tracing function calling with Azure OpenAI
3. `structured_output.py` - Tracing structured outputs (JSON responses)
4. `reasoning_models.py` - Tracing reasoning models (where supported by Azure OpenAI)
5. `multi_turn_conversation.py` - Tracing multi-turn conversations

Each example shows how HoneyHive automatically traces Azure OpenAI API calls and how you can enhance traces with additional context.

## Viewing Traces

After running any of the examples, you can view the traces in your HoneyHive dashboard. The traces include:

- Request and response payloads
- Latency metrics
- Token usage
- Custom attributes
- Errors and exceptions

## Additional Resources

- [HoneyHive Documentation](https://docs.honeyhive.ai/)
- [Azure OpenAI Documentation](https://learn.microsoft.com/azure/ai-services/openai/)
- [OpenTelemetry Documentation](https://opentelemetry.io/docs/) 