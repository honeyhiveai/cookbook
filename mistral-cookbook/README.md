# Mistral AI Integration Cookbook for HoneyHive

This cookbook demonstrates how to integrate [Mistral AI](https://mistral.ai/) with HoneyHive for observability in Large Language Model (LLM) applications.

## Overview

Mistral AI is a model provider offering cutting-edge large language models, including the open-source Mistral 7B model. Mistral provides a cloud API that allows you to use their models for inference without hosting them yourself.

This cookbook covers:
- Setting up authentication with Mistral AI
- Making inference calls to Mistral's models
- Integrating with HoneyHive for observability
- Building applications with Mistral's chat completion and embedding capabilities

## Contents

- `mistral_integration.ipynb`: Jupyter notebook with step-by-step examples
- `README.md`: This documentation file

## Prerequisites

- Python 3.8+
- Mistral AI account and API key
- HoneyHive account and API key

## Quick Start

1. Install the required packages:
   ```bash
   pip install mistralai==0.2.0 honeyhive
   ```

2. Set up your environment variables:
   ```bash
   export MISTRAL_API_KEY="your_mistral_api_key"
   export HONEYHIVE_API_KEY="your_honeyhive_api_key"
   ```

3. Open and run the Jupyter notebook:
   ```bash
   jupyter notebook mistral_integration.ipynb
   ```

## Key Features

- **Mistral Cloud API**: Connect to Mistral's hosted models
- **Chat Completion**: Generate text responses with Mistral's models
- **Streaming Support**: Stream tokens incrementally for real-time applications
- **Embeddings**: Generate vector representations of text
- **HoneyHive Tracing**: Automatic instrumentation of Mistral API calls
- **Performance Monitoring**: Track latency and model performance

## Model Options

Mistral offers several model variants, including:
- `mistral-small-latest`: Optimized for speed
- `mistral-medium-latest`: Balanced performance
- `mistral-large-latest`: Highest quality responses
- `mistral-embed`: For generating embeddings

## Additional Resources

- [Mistral AI Documentation](https://docs.mistral.ai/)
- [HoneyHive Documentation](https://docs.honeyhive.ai/)
- [Mistral AI GitHub](https://github.com/mistralai)

## Support

For questions about this cookbook, please contact the HoneyHive team or visit [honeyhive.ai](https://honeyhive.ai). 