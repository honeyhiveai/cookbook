# Observability Tutorial (Python)

This directory contains a script demonstrating how to implement observability in a RAG (Retrieval-Augmented Generation) pipeline using OpenAI, Pinecone, and HoneyHive for tracing and evaluation.

## Prerequisites

- Python 3.7+
- OpenAI API key
- Pinecone API key
- HoneyHive API key
- Pinecone index set up

## Setup

1. Clone this repository:
   ```
   git clone https://github.com/honeyhiveai/cookbook
   cd observability-tutorial-python
   ```

2. Create a Python virtual environment:
   ```
   python -m venv observability_env
   source observability_env/bin/activate  # On Windows use `observability_env\Scripts\activate`
   ```

3. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

4. Update the API keys and project name in `observability_tutorial.py`:
   - Replace `your-honeyhive-api-key` with your HoneyHive API key
   - Replace `your-honeyhive-project-name` with your HoneyHive project name
   - Replace `your-index-name` with your Pinecone index name
   - Uncomment and update the OpenAI and Pinecone API key environment variables

## Usage

Run the script:
```
python observability_tutorial.py
```

## How It Works

This script demonstrates a RAG pipeline with observability using HoneyHive. Here's a breakdown of what the script does:

1. Imports necessary libraries and sets up API clients
2. Initializes HoneyHive Tracer for observability
3. Defines functions for embedding queries, retrieving relevant documents, and generating responses
4. Implements a RAG pipeline that combines document retrieval and response generation
5. Uses HoneyHive's `@trace` decorator to log function calls and their metadata
6. Simulates user feedback and logs it using HoneyHive

The script uses OpenAI's API for embeddings and text generation, Pinecone for vector search, and HoneyHive for tracing and observability.

## File Structure

- `observability_tutorial.py`: The main Python script demonstrating the RAG pipeline with observability
- `README.md`: This file, containing instructions and explanations
- `requirements.txt`: File containing package requirements (not shown in the provided snippets)

## Notes

- Ensure you keep your API keys confidential and do not commit them to version control.
- The script uses OpenAI's "text-embedding-ada-002" for embeddings and "gpt-4o" for text generation. Adjust these if needed.
- The Pinecone index should be set up beforehand with appropriate data for the RAG pipeline to work effectively.
- Observability data will be available in your HoneyHive project for analysis and evaluation.