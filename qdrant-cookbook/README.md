# Qdrant RAG Pipeline with HoneyHive Tracing

This cookbook demonstrates how to build a Retrieval-Augmented Generation (RAG) pipeline using Qdrant as the vector store, with HoneyHive for end-to-end observability.

## Overview

The example covers:
- Connecting to Qdrant (local or cloud)
- Embedding documents with OpenAI
- Storing and searching vectors in Qdrant
- Generating answers with context from retrieved documents
- Tracing the entire RAG pipeline with HoneyHive

## Setup

### Prerequisites

- Python 3.11+
- A running Qdrant instance (local via Docker or Qdrant Cloud)
- OpenAI and HoneyHive API keys

### Start Qdrant locally

```bash
docker pull qdrant/qdrant
docker run -p 6333:6333 -p 6334:6334 -v "$(pwd)/qdrant_storage:/qdrant/storage" qdrant/qdrant
```

### Install dependencies

```bash
git clone https://github.com/honeyhiveai/cookbook.git
cd cookbook/qdrant-cookbook
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

### Configuration

Create a `.env` file:

```bash
HH_API_KEY=your-honeyhive-api-key
HH_PROJECT=qdrant-rag-example
OPENAI_API_KEY=your-openai-api-key
```

### Run

```bash
uv run python qdrant_integration.py
```

## How it works

The `OpenAIInstrumentor` automatically traces all OpenAI embedding and chat completion calls. Business logic functions use `@trace` decorators for custom spans:

```python
from honeyhive import HoneyHiveTracer, trace
from openinference.instrumentation.openai import OpenAIInstrumentor

tracer = HoneyHiveTracer.init(
    api_key=os.getenv("HH_API_KEY"),
    project=os.getenv("HH_PROJECT"),
)
OpenAIInstrumentor().instrument(tracer_provider=tracer.provider)
```

## References

- [HoneyHive Documentation](https://docs.honeyhive.ai/)
- [Qdrant Documentation](https://qdrant.tech/documentation/)
- [OpenAI API Documentation](https://platform.openai.com/docs/api-reference)
