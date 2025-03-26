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

- Python 3.8+
- An OpenAI API key
- A HoneyHive API key

### Installation

```bash
pip install openai honeyhive
```

### Configuration

Set your API keys as environment variables or directly in the code (for demonstration purposes only):

```python
import os
from openai import OpenAI
from honeyhive import HoneyHiveTracer

# Initialize HoneyHive tracer
HoneyHiveTracer.init(
    api_key="your_honeyhive_api_key",
    project="OpenAI-traces"
)

# Initialize OpenAI client
client = OpenAI(api_key="your_openai_api_key")
```

## Examples

This cookbook contains the following examples:

1. `basic_chat.py` - Tracing basic chat completions
2. `function_calling.py` - Tracing function calling with OpenAI
3. `structured_output.py` - Tracing structured outputs (JSON responses)
4. `reasoning_models.py` - Tracing reasoning models (o1, o3-mini)
5. `multi_turn_conversation.py` - Tracing multi-turn conversations

Each example shows how HoneyHive automatically traces OpenAI API calls and how you can enhance traces with additional context.

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
- [OpenTelemetry Documentation](https://opentelemetry.io/docs/) 