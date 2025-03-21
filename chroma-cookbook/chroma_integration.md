---
title: 'HoneyHive with Chroma'
description: 'Learn how to integrate HoneyHive tracing with Chroma vector database for RAG applications'
---

# Chroma Integration with HoneyHive

This guide demonstrates how to integrate HoneyHive tracing with [Chroma](https://www.trychroma.com/), an open-source embedding database, to monitor and optimize your RAG (Retrieval Augmented Generation) applications.

## Prerequisites

- A HoneyHive account and API key
- Python 3.8+
- Basic understanding of vector databases and RAG pipelines

## Installation

First, install the required packages:

```bash
pip install honeyhive chromadb openai
```

## Setup and Configuration

### Initialize HoneyHive Tracer

Start by initializing the HoneyHive tracer at the beginning of your application:

```python
import os
from honeyhive import HoneyHiveTracer

# Set your API keys
HONEYHIVE_API_KEY = "your honeyhive api key"
OPENAI_API_KEY = "your openai api key"

# Initialize OpenAI client
from openai import OpenAI
client = OpenAI(api_key=OPENAI_API_KEY)

# Initialize HoneyHive tracer
HoneyHiveTracer.init(
    api_key=HONEYHIVE_API_KEY,
    project="multi-test",
    source="dev",
    session_name="chroma_rag_example"
)
```

### Initialize Chroma Client

Next, set up the connection to your Chroma database:

```python
import chromadb
from honeyhive import trace

@trace
def initialize_chroma_client(persist_directory="./chroma_db"):
    """Initialize and return a Chroma client with the specified persistence directory."""
    try:
        client = chromadb.PersistentClient(path=persist_directory)
        print(f"Initialized Chroma client with persistence at: {persist_directory}")
        return client
    except Exception as e:
        print(f"Error initializing Chroma client: {e}")
        raise

# Define collection name
COLLECTION_NAME = "honeyhive_chroma_demo"
```

## Tracing Chroma Operations

### Create Collection with Tracing

Use the `@trace` decorator to monitor collection creation:

```python
@trace
def create_chroma_collection(client):
    """Create a Chroma collection if it doesn't exist."""
    try:
        # Get or create collection
        collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=None  # We'll use OpenAI embeddings separately
        )
        print(f"Using collection: {COLLECTION_NAME}")
        return collection
    except Exception as e:
        print(f"Error creating collection: {e}")
        raise
```

### Generate Embeddings with Tracing

Trace the embedding generation process:

```python
@trace
def generate_embeddings(texts):
    """Generate embeddings for a list of texts using OpenAI."""
    try:
        response = client.embeddings.create(
            model="text-embedding-ada-002",
            input=texts
        )
        embeddings = [item.embedding for item in response.data]
        print(f"Generated {len(embeddings)} embeddings")
        return embeddings
    except Exception as e:
        print(f"Error generating embeddings: {e}")
        raise
```

### Add Documents with Tracing

Trace the document addition process:

```python
@trace
def add_documents_to_chroma(collection, documents):
    """Add documents to the Chroma collection."""
    try:
        # Extract text, ids, and metadata
        texts = [doc["text"] for doc in documents]
        ids = [doc["_id"] for doc in documents]
        metadatas = [{"source": doc.get("source", "unknown")} for doc in documents]
        
        # Generate embeddings
        embeddings = generate_embeddings(texts)
        
        # Add documents to collection
        collection.add(
            embeddings=embeddings,
            documents=texts,
            ids=ids,
            metadatas=metadatas
        )
        print(f"Added {len(documents)} documents to collection")
    except Exception as e:
        print(f"Error adding documents: {e}")
        raise
```

### Search with Tracing

Monitor search operations:

```python
@trace
def search_chroma(collection, query, limit=3):
    """Search the Chroma collection for relevant documents."""
    try:
        # Generate embedding for query
        query_embedding = generate_embeddings([query])[0]
        
        # Search the collection
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=limit
        )
        
        # Format results
        formatted_results = []
        for i in range(len(results["ids"][0])):
            formatted_results.append({
                "_id": results["ids"][0][i],
                "text": results["documents"][0][i],
                "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                "distance": results["distances"][0][i] if "distances" in results else None
            })
        
        print(f"Found {len(formatted_results)} results for query: {query}")
        return formatted_results
    except Exception as e:
        print(f"Error searching collection: {e}")
        raise
```

## Complete RAG Pipeline Example

Here's a complete example of a RAG pipeline using Chroma and HoneyHive tracing:

```python
import os
import chromadb
from openai import OpenAI
from honeyhive import HoneyHiveTracer, trace

# Set your API keys
HONEYHIVE_API_KEY = "your honeyhive api key"
OPENAI_API_KEY = "your openai api key"

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

# Initialize HoneyHive tracer
HoneyHiveTracer.init(
    api_key=HONEYHIVE_API_KEY,
    project="multi-test",
    source="dev",
    session_name="chroma_rag_example"
)

@trace
def initialize_chroma_client(persist_directory="./chroma_db"):
    # Implementation as shown above
    pass

@trace
def create_chroma_collection(client):
    # Implementation as shown above
    pass

@trace
def generate_embeddings(texts):
    # Implementation as shown above
    pass

@trace
def add_documents_to_chroma(collection, documents):
    # Implementation as shown above
    pass

@trace
def search_chroma(collection, query, limit=3):
    # Implementation as shown above
    pass

@trace
def generate_response(query, context):
    """Generate a response using OpenAI based on the retrieved context."""
    try:
        # Extract text from context
        context_text = "\n\n".join([doc.get("text", "") for doc in context])
        
        # Create prompt
        prompt = f"""
        Answer the following question based on the provided context:
        
        Context:
        {context_text}
        
        Question: {query}
        
        Answer:
        """
        
        # Call OpenAI API
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that answers questions based on the provided context."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=500
        )
        
        answer = response.choices[0].message.content
        return answer
    except Exception as e:
        print(f"Error generating response: {e}")
        raise

@trace
def rag_pipeline(query, documents=None):
    """
    Run the complete RAG pipeline with Chroma and HoneyHive tracing.
    
    Args:
        query: The user query
        documents: Optional list of documents to add to the collection
    
    Returns:
        The generated response
    """
    # Initialize Chroma client
    client = initialize_chroma_client()
    
    # Create collection
    collection = create_chroma_collection(client)
    
    # Add documents if provided
    if documents:
        add_documents_to_chroma(collection, documents)
    
    # Search for relevant documents
    results = search_chroma(collection, query)
    
    # Generate response
    response = generate_response(query, results)
    
    return response

def main():
    # Sample documents
    documents = [
        {"text": "Chroma is an open-source embedding database designed for AI applications.", "_id": "1", "source": "docs"},
        {"text": "HoneyHive provides tracing and monitoring for AI applications.", "_id": "2", "source": "docs"},
        {"text": "Retrieval Augmented Generation (RAG) combines retrieval systems with generative models.", "_id": "3", "source": "docs"},
        {"text": "Vector databases store embeddings which are numerical representations of data.", "_id": "4", "source": "docs"},
        {"text": "OpenTelemetry is an observability framework for cloud-native software.", "_id": "5", "source": "docs"}
    ]
    
    # Sample query
    query = "How can HoneyHive help with RAG applications?"
    
    # Run the RAG pipeline
    response = rag_pipeline(query, documents)
    
    print("\n=== Generated Response ===")
    print(response)
    
if __name__ == "__main__":
    main()
```

## What's Being Traced

With this integration, HoneyHive captures:

1. **Client Initialization**: Configuration and performance of Chroma client setup
2. **Collection Creation**: Time taken to create or access the collection
3. **Embedding Generation**: Performance metrics for the embedding model
4. **Document Addition**: Time taken and success rate of adding documents to Chroma
5. **Search Operations**: Query execution time, number of results, and search parameters
6. **Response Generation**: LLM prompt construction and response generation time
7. **Overall Pipeline Performance**: End-to-end execution time and resource utilization

## Viewing Traces in HoneyHive

After running your application:

1. Log into your HoneyHive account
2. Navigate to your project
3. View the traces in the Sessions tab
4. Analyze the performance of each component in your RAG pipeline

## Best Practices

- Use descriptive session names to easily identify different runs
- Add custom attributes to traces for more detailed analysis
- Consider using Chroma's built-in embedding functions for simpler code
- Trace both successful operations and error handling paths
- Experiment with different persistence configurations to optimize performance

## Troubleshooting

If you encounter issues with tracing:

- Ensure your HoneyHive API key is correct
- Check that the Chroma persistence directory is writable
- Verify that all required packages are installed
- Review the HoneyHive documentation for additional troubleshooting steps

## Next Steps

- Experiment with different embedding models
- Add custom metrics to your traces
- Implement A/B testing of different RAG configurations
- Explore HoneyHive's evaluation capabilities for your RAG pipeline

By integrating HoneyHive with Chroma, you gain valuable insights into your vector search operations and can optimize your RAG pipeline for better performance and accuracy.
