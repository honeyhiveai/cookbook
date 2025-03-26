# LanceDB with HoneyHive Tracing

This cookbook demonstrates how to implement a simple RAG (Retrieval Augmented Generation) pipeline using LanceDB with HoneyHive tracing for observability.

## Overview

The main example in this cookbook (`lancedb_rag_with_tracing.py`) shows how to:

1. Load and chunk documents
2. Create a vector store using LanceDB
3. Retrieve relevant documents based on a query
4. Generate an answer using OpenAI
5. Trace the entire pipeline with HoneyHive for observability

## Prerequisites

Before running the examples, you'll need:

1. Python 3.9+ installed
2. An OpenAI API key
3. A HoneyHive API key and project name

## Installation

Install the required dependencies:

```bash
pip install lancedb honeyhive sentence-transformers openai pandas
```

## Environment Setup

Create a `.env` file in the lancedb-cookbook directory with the following content:

```
OPENAI_API_KEY=your_openai_api_key
HONEYHIVE_API_KEY=your_honeyhive_api_key
HONEYHIVE_PROJECT=your_honeyhive_project_name
```

Alternatively, you can set these environment variables in your shell:

```bash
export OPENAI_API_KEY=your_openai_api_key
export HONEYHIVE_API_KEY=your_honeyhive_api_key
export HONEYHIVE_PROJECT=your_honeyhive_project_name
```

## Running the Example

Run the simple RAG pipeline with HoneyHive tracing:

```bash
python lancedb_rag_with_tracing.py
```

This will:
1. Create a sample dataset if it doesn't exist
2. Run a RAG pipeline with the query "What is LanceDB and how can it be used for RAG?"
3. Trace all steps with HoneyHive
4. Print the final answer

## Components

### Document Loading and Chunking

The example loads documents from a text file and chunks them into smaller pieces for embedding.

### Vector Store Creation

It creates a LanceDB table with embeddings using the sentence-transformers model "BAAI/bge-small-en-v1.5".

### Document Retrieval

The example retrieves relevant documents from LanceDB based on the query.

### Answer Generation

It generates an answer using OpenAI's GPT-3.5-turbo model based on the retrieved documents.

## HoneyHive Integration

The example uses HoneyHive to trace:

1. Document loading and chunking
2. Vector store creation
3. Document retrieval
4. Answer generation
5. The entire RAG pipeline

### Key Components

- **@trace decorator**: Applied to functions to trace their execution
- **HoneyHiveTracer.init()**: Initializes HoneyHive tracing with your API key and project

### Viewing Traces

After running the example, you can view the traces in the HoneyHive dashboard:

1. Log in to your HoneyHive account
2. Navigate to the project you specified
3. View the traces under the session name "lancedb_rag_session"

## Customization

You can customize this example by:

1. Changing the sample data in the `main()` function
2. Modifying the query
3. Adjusting the chunk size or retrieval limit
4. Using a different embedding model

## Troubleshooting

If you encounter issues:

1. Ensure your API keys are correct
2. Check that you have installed all dependencies
3. Verify that you have internet access for API calls
4. Check the HoneyHive dashboard for any error messages
5. Look at the log file "rag_pipeline.log" for detailed logs

## Additional Resources

- [HoneyHive Documentation](https://docs.honeyhive.ai/)
- [LanceDB Documentation](https://lancedb.github.io/lancedb/)
- [OpenAI API Documentation](https://platform.openai.com/docs/api-reference)
- [Sentence Transformers Documentation](https://www.sbert.net/) 