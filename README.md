# HoneyHive Cookbooks

Integration examples for AI observability and evaluation with HoneyHive.

[Website](https://honeyhive.ai) · [Documentation](https://docs.honeyhive.ai) · [Community](https://discord.com/invite/vqctGpqA97) · [Blog](https://www.honeyhive.ai/blog)

## Available Cookbooks

### Multi-Agent Systems

| Cookbook | Description |
|----------|-------------|
| [google-adk-cookbook](./google-adk-cookbook) | Multi-agent customer support example with Google ADK, HoneyHive tracing, and evaluation |
| [wealth-management-agent](./wealth-management-agent) | Multi-agent wealth advisory platform with HoneyHive tracing (CrewAI) |

### RAG & Vector Databases

| Cookbook | Description |
|----------|-------------|
| [qdrant-cookbook](./qdrant-cookbook) | RAG pipeline with Qdrant vector database and HoneyHive tracing |

### LLM Provider Integrations

| Cookbook | Description |
|----------|-------------|
| [openai-honeyhive-cookbook](./openai-honeyhive-cookbook) | HoneyHive tracing for OpenAI API (chat, function calling, structured outputs, reasoning) |
| [aws-bedrock-honeyhive-cookbook](./aws-bedrock-honeyhive-cookbook) | HoneyHive tracing for AWS Bedrock models |
| [azure-openai-honeyhive-cookbook](./azure-openai-honeyhive-cookbook) | HoneyHive tracing for Azure OpenAI (chat, function calling, structured outputs, reasoning) |

### Domain-Specific

| Cookbook | Description |
|----------|-------------|
| [claims-summarizer-python](./claims-summarizer-python) | Insurance claims summarization with AWS Bedrock and HoneyHive (Python) |

### Legacy

Older cookbooks that have not been updated to the latest SDK are in [legacy_cookbooks](./legacy_cookbooks).

## Getting Started

Each cookbook contains its own README with specific instructions. All Python cookbooks use the v2 SDK (`honeyhive>=1.0.0`) with OpenInference instrumentors for automatic framework tracing.

1. Sign up at [honeyhive.ai](https://honeyhive.ai) and get your API key
2. Clone the repo:
   ```bash
   git clone https://github.com/honeyhiveai/cookbook.git
   cd cookbook
   ```
3. Navigate to the cookbook that matches your use case and follow its README

## Requirements

- **Python 3.11+** for Python examples
- **Node.js 18+** for JavaScript examples
- **API Keys** for relevant services (HoneyHive, OpenAI, AWS, Azure, etc.)

## Support

- [Open an issue](https://github.com/honeyhiveai/cookbook/issues/new)
- Contact the HoneyHive team at support@honeyhive.ai
- Visit [honeyhive.ai](https://honeyhive.ai)
