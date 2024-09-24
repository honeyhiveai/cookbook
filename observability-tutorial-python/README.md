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

4. Create a `.env` file in the project root and add your API keys:
   ```
   OPENAI_API_KEY=your-openai-api-key
   PINECONE_API_KEY=your-pinecone-api-key
   HONEYHIVE_API_KEY=your-honeyhive-api-key
   HONEYHIVE_PROJECT=your-honeyhive-project-name
   ```

5. Update the script to use environment variables:
   - In `observability_tutorial.py`, replace the hardcoded API keys and project names with `os.getenv()` calls.
   - Replace `your-index-name` with the name of your Pinecone index.

## Usage

Run the script:
```
python observability_tutorial.py
```

## Docker Support (Optional)

If you prefer to use Docker, follow these steps:

1. Build the Docker image:
   ```
   docker build -t observability-tutorial-python .
   ```

2. Run the Docker container:
   ```
   docker run --env-file .env observability-tutorial-python
   ```

This will run the application inside a Docker container, using the environment variables from your `.env` file.

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
- `requirements.txt`: File containing package requirements
- `Dockerfile`: Configuration file for building a Docker image (if using Docker)
- `.env`: File for storing environment variables (not included in repository)

## Notes

- Ensure you keep your API keys confidential and do not commit them to version control.
- The script uses OpenAI's "text-embedding-ada-002" for embeddings and "gpt-4o" for text generation. Adjust these if needed.
- The Pinecone index should be set up beforehand with appropriate data for the RAG pipeline to work effectively.
- Observability data will be available in your HoneyHive project for analysis and evaluation.

## Dependencies

The main dependencies for this project are:

- `openai`: For OpenAI API interactions
- `pinecone`: For vector database operations
- `honeyhive`: For observability and tracing

Refer to `requirements.txt` for the complete list of dependencies and their versions.