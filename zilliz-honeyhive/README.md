# Zilliz-HoneyHive Integration: RAG Pipeline with Observability

This repository demonstrates how to build a Retrieval-Augmented Generation (RAG) pipeline using Zilliz/Milvus as the vector database and HoneyHive for observability and tracing.

## Overview

This project showcases:

1. Setting up a Milvus vector database (using Milvus Lite for local development)
2. Creating embeddings with OpenAI
3. Building a complete RAG pipeline with document retrieval and generation
4. Implementing observability with HoneyHive to track and analyze the performance of your RAG system

## Prerequisites

- Python 3.8+
- OpenAI API key
- HoneyHive API key

## Installation

Install the required packages:

```bash
pip install openai pymilvus honeyhive
```

## Components

### 1. Milvus Vector Database

[Milvus](https://milvus.io/) is an open-source vector database built to power embedding similarity search and AI applications. This project uses:

- **Milvus Lite**: A lightweight version of Milvus that runs locally, perfect for development and testing
- **Collection Management**: Creating and configuring vector collections
- **Vector Search**: Performing similarity searches with filters

### 2. OpenAI Embeddings and Generation

- **Text Embeddings**: Using OpenAI's `text-embedding-ada-002` model to convert text into vector representations
- **Text Generation**: Using GPT models to generate responses based on retrieved context

### 3. HoneyHive Observability

[HoneyHive](https://www.honeyhive.ai/) provides observability for AI applications, allowing you to:

- **Trace RAG Pipeline Steps**: Monitor each step of your RAG pipeline
- **Analyze Performance**: Identify bottlenecks and areas for improvement
- **Track Model Usage**: Monitor token usage and latency

## Project Structure

The main notebook (`quickstart-zilliz-python.ipynb`) demonstrates:

1. Setting up the environment and initializing clients
2. Creating a Milvus collection with proper schema
3. Embedding and inserting documents
4. Implementing a search function to retrieve similar documents
5. Building a complete RAG pipeline with tracing
6. Generating responses based on retrieved context

## Usage

1. Open the Jupyter notebook: `quickstart-zilliz-python.ipynb`
2. Replace the API keys with your own:
   ```python
   # Initialize HoneyHive Tracer
   HoneyHiveTracer.init(
       api_key="Your HoneyHive key",
       project="name of your project",
   )
   
   # Initialize OpenAI client
   openai_client = OpenAI(api_key="your OpenAI key")
   ```
3. Run the notebook cells to see the RAG pipeline in action

## Key Functions

### Setting Up Milvus Collection

```python
@trace(
    config={
        "collection_name": "demo_collection",
        "dimension": 1536,  # text-embedding-ada-002 dimension
    }
)
def setup_collection():
    """Set up Milvus collection with tracing"""
    # Drop collection if it exists
    if milvus_client.has_collection(collection_name="demo_collection"):
        milvus_client.drop_collection(collection_name="demo_collection")

    # Create new collection
    milvus_client.create_collection(
        collection_name="demo_collection",
        dimension=1536  # text-embedding-ada-002 dimension
    )
```

### Inserting Documents

```python
@trace(
    config={
        "embedding_model": "text-embedding-ada-002"
    }
)
def insert_documents(documents):
    """Insert documents with tracing"""
    vectors = [embed_text(doc) for doc in documents]
    data = [
        {
            "id": i,
            "vector": vectors[i],
            "text": documents[i],
            "subject": "general"
        }
        for i in range(len(vectors))
    ]

    res = milvus_client.insert(
        collection_name="demo_collection",
        data=data
    )
    return res
```

### Searching Similar Documents

```python
@trace(
    config={
        "embedding_model": "text-embedding-ada-002",
        "top_k": 3
    }
)
def search_similar_documents(query, top_k=3):
    """Search for similar documents with tracing"""
    query_vector = embed_text(query)

    results = milvus_client.search(
        collection_name="demo_collection",
        data=[query_vector],
        limit=top_k,
        output_fields=["text", "subject"]
    )

    return [match["entity"]["text"] for match in results[0]]
```

### Complete RAG Pipeline

```python
@trace()
def rag_pipeline(query):
    """Complete RAG pipeline with tracing"""
    # Get relevant documents
    relevant_docs = search_similar_documents(query)
    # Generate response
    response = generate_response("\\n".join(relevant_docs), query)
    return response
```

## Advanced Features

### Metadata Filtering

Milvus supports filtering based on metadata, allowing you to narrow down search results:

```python
results = milvus_client.search(
    collection_name="demo_collection",
    data=[query_vector],
    limit=top_k,
    output_fields=["text", "subject"],
    filter="subject == 'science'"  # Only return documents with subject='science'
)
```

### Multi-Tenancy

For applications serving multiple users, you can use Milvus's partition key feature:

```python
# Create collection with partition key
milvus_client.create_collection(
    collection_name="multi_tenant_collection",
    dimension=1536,
    partition_key_field="user_id"
)

# Search only within a specific user's data
results = milvus_client.search(
    collection_name="multi_tenant_collection",
    data=[query_vector],
    limit=top_k,
    expr='user_id == "user123"'
)
```

## HoneyHive Observability Tips

1. **Session Management**: Use meaningful session names to group related operations
   ```python
   HoneyHiveTracer.init(
       api_key="your-key",
       project="your-project",
       session_name="user-session-123"
   )
   ```

2. **Disable Batching for Notebooks**: For Jupyter notebooks, disable batching to ensure data is sent immediately
   ```python
   HoneyHiveTracer.init(
       api_key="your-key",
       project="your-project",
       disable_batch=True
   )
   ```

3. **Flush at End of Script**: For scripts, ensure all data is sent by flushing at the end
   ```python
   # At the end of your script
   HoneyHiveTracer.flush()
   ```

## Resources

- [Milvus Documentation](https://milvus.io/docs)
- [HoneyHive Documentation](https://docs.honeyhive.ai/)
- [OpenAI API Documentation](https://platform.openai.com/docs/api-reference)
