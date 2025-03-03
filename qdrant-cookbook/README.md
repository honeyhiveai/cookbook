# Qdrant Integration Cookbook for HoneyHive

This cookbook demonstrates how to integrate [Qdrant](https://qdrant.tech/) (a vector database) with HoneyHive for observability in Retrieval-Augmented Generation (RAG) pipelines.

## Overview

Qdrant is an open-source vector database optimized for storing and searching high-dimensional embeddings. In a RAG pipeline, Qdrant serves as the "long-term memory" for your LLM, efficiently managing storage and retrieval of document vectors.

This cookbook covers:
- Setting up Qdrant (both self-hosted and cloud-hosted options)
- Integrating Qdrant with HoneyHive for observability
- Building a complete RAG pipeline with Qdrant as the vector store
- Tracing and monitoring your vector operations

## Contents

- `qdrant_integration.ipynb`: Jupyter notebook with step-by-step examples
- `README.md`: This documentation file

## Prerequisites

- Python 3.8+
- Docker (for self-hosted Qdrant)
- HoneyHive account and API key
- OpenAI API key (for embeddings and LLM in the example)

## Quick Start

1. Install the required packages:
   ```bash
   pip install qdrant-client openai honeyhive
   ```

2. Run Qdrant locally using Docker:
   ```bash
   docker pull qdrant/qdrant
   docker run -p 6333:6333 -p 6334:6334 -v "$(pwd)/qdrant_storage:/qdrant/storage" qdrant/qdrant
   ```

3. Open and run the Jupyter notebook:
   ```bash
   jupyter notebook qdrant_integration.ipynb
   ```

## Key Features

- **Self-hosted & Cloud Options**: Instructions for both local Qdrant and Qdrant Cloud
- **Complete RAG Pipeline**: From document embedding to retrieval and answer generation
- **HoneyHive Tracing**: Automatic instrumentation of Qdrant operations
- **Performance Monitoring**: Track latency and effectiveness of vector operations

## Additional Resources

- [Qdrant Documentation](https://qdrant.tech/documentation/)
- [HoneyHive Documentation](https://docs.honeyhive.ai/)
- [Qdrant Python Client](https://python-client.qdrant.tech/)

## Support

For questions about this cookbook, please contact the HoneyHive team or visit [honeyhive.ai](https://honeyhive.ai). 