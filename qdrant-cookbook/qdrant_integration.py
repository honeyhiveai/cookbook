"""
# Qdrant Integration with HoneyHive

This script demonstrates how to integrate Qdrant (a vector database) with HoneyHive for 
observability in Retrieval-Augmented Generation (RAG) pipelines.

## Overview

Qdrant is an open-source vector database optimized for storing and searching high-dimensional 
embeddings. In a RAG pipeline, Qdrant serves as the "long-term memory" for your LLM, 
efficiently managing storage and retrieval of document vectors.

This script covers:
1. Setting up Qdrant (both self-hosted and cloud options)
2. Initializing HoneyHive for observability
3. Building a complete RAG pipeline with Qdrant as the vector store
4. Tracing and monitoring vector operations
"""

# 1. Installation and Setup
# First, install the required packages:
# pip install qdrant-client openai honeyhive

# Import Libraries
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct
import openai
import os
from honeyhive.tracer import HoneyHiveTracer
from honeyhive.tracer.custom import trace  # for custom span annotation

# Set API Keys
openai.api_key = os.getenv("OPENAI_API_KEY", "your_openai_api_key")

# Initialize HoneyHive Tracer
HoneyHiveTracer.init(
    api_key=os.getenv("HONEYHIVE_API_KEY", "your_honeyhive_api_key"),
    project="qdrant-rag-example",  # Your project name in HoneyHive
    session_name="qdrant-integration-demo"  # Optional session identifier
)

# 2. Connect to Qdrant
# You can connect to Qdrant in two ways: self-hosted (local) or cloud-hosted (Qdrant Cloud)

# Option 1: Self-Hosted Qdrant (Local)
# To run Qdrant locally, you need to have Docker installed and run the following command:
# docker pull qdrant/qdrant
# docker run -p 6333:6333 -p 6334:6334 -v "$(pwd)/qdrant_storage:/qdrant/storage" qdrant/qdrant

# Connect to local Qdrant
client = QdrantClient(url="http://localhost:6333")
print("Connected to local Qdrant instance")

# Option 2: Qdrant Cloud (uncomment to use)
# QDRANT_HOST = "your-cluster-id.eu-central.aws.cloud.qdrant.io"  # Replace with your cluster host
# QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "your_qdrant_api_key")  # Replace with your API key
# client = QdrantClient(host=QDRANT_HOST, api_key=QDRANT_API_KEY)
# print("Connected to Qdrant Cloud")

# 3. Create a Collection
# Let's create a collection to store our document embeddings
collection_name = "documents"

# Check if collection exists, if not create it
if not client.collection_exists(collection_name):
    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=1536, distance=Distance.COSINE)
    )
    print(f"Collection '{collection_name}' created")
else:
    print(f"Collection '{collection_name}' already exists")

# 4. Define Embedding Function
@trace(config={"model": "text-embedding-ada-002"})
def embed_text(text: str) -> list:
    """Generate embeddings for a text using OpenAI's API."""
    response = openai.Embedding.create(
        model="text-embedding-ada-002",
        input=text
    )
    return response['data'][0]['embedding']

# 5. Insert Documents into Qdrant
# Sample documents
documents = [
    "Qdrant is a vector database optimized for storing and searching high-dimensional vectors.",
    "HoneyHive provides observability for AI applications, including RAG pipelines.",
    "Retrieval-Augmented Generation (RAG) combines retrieval systems with generative models.",
    "Vector databases like Qdrant are essential for efficient similarity search in RAG systems.",
    "OpenAI's embedding models convert text into high-dimensional vectors for semantic search."
]

@trace(config={"operation": "upsert_documents", "count": len(documents)})
def insert_documents(docs):
    """Insert documents into Qdrant collection."""
    points = []
    for idx, doc in enumerate(docs):
        vector = embed_text(doc)
        points.append(PointStruct(
            id=str(idx),
            vector=vector,
            payload={"text": doc}
        ))
    
    # Upsert points to Qdrant
    client.upsert(
        collection_name=collection_name,
        points=points
    )
    return len(points)

# Insert documents
num_inserted = insert_documents(documents)
print(f"Inserted {num_inserted} documents into Qdrant")

# 6. Define Retrieval Function
@trace(config={"top_k": 3, "embedding_model": "text-embedding-ada-002"})
def get_relevant_docs(query: str, top_k: int = 3) -> list:
    """Retrieve relevant documents for a query."""
    # Embed the query
    q_vector = embed_text(query)
    
    # Search in Qdrant for similar vectors
    search_results = client.search(
        collection_name=collection_name,
        query_vector=q_vector,
        limit=top_k,
        with_payload=True  # ensure we get stored payload (text)
    )
    
    # Extract the text payload from each result
    docs = []
    for point in search_results:
        docs.append({
            "text": point.payload.get("text"),
            "score": point.score  # similarity score
        })
    
    return docs

# 7. Define Answer Generation Function
@trace(config={"model": "gpt-3.5-turbo", "prompt_template": "RAG Q&A"})
def answer_query(query: str) -> str:
    """Generate an answer for a query using retrieved documents."""
    # Get relevant documents
    relevant_docs = get_relevant_docs(query)
    
    # Format context from retrieved documents
    context = "\n\n".join([f"Document {i+1} (Score: {doc['score']:.4f}):\n{doc['text']}" 
                          for i, doc in enumerate(relevant_docs)])
    
    # Create prompt with context and query
    prompt = f"""Answer the question based on the following context:

Context:
{context}

Question: {query}

Answer:"""
    
    # Generate answer using OpenAI
    completion = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that answers questions based on the provided context."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )
    
    answer = completion['choices'][0]['message']['content']
    return answer

# 8. Complete RAG Pipeline
@trace()
def rag_pipeline(query: str) -> dict:
    """End-to-end RAG pipeline."""
    # Get relevant documents
    relevant_docs = get_relevant_docs(query)
    
    # Generate answer
    answer = answer_query(query)
    
    # Return both the answer and the retrieved documents
    return {
        "query": query,
        "answer": answer,
        "retrieved_documents": relevant_docs
    }

# 9. Test the RAG Pipeline
def test_rag_pipeline():
    # Example query 1
    query1 = "What is Qdrant used for?"
    result1 = rag_pipeline(query1)
    
    print(f"Query: {result1['query']}")
    print(f"Answer: {result1['answer']}")
    print("\nRetrieved Documents:")
    for i, doc in enumerate(result1['retrieved_documents']):
        print(f"Document {i+1} (Score: {doc['score']:.4f}): {doc['text']}")
    
    # Example query 2
    query2 = "How does HoneyHive help with RAG pipelines?"
    result2 = rag_pipeline(query2)
    
    print(f"\nQuery: {result2['query']}")
    print(f"Answer: {result2['answer']}")
    print("\nRetrieved Documents:")
    for i, doc in enumerate(result2['retrieved_documents']):
        print(f"Document {i+1} (Score: {doc['score']:.4f}): {doc['text']}")

# 10. Advanced: Batch Processing
@trace(config={"operation": "batch_insert"})
def batch_insert_documents(documents, batch_size=10):
    """Insert documents in batches."""
    total_inserted = 0
    
    for i in range(0, len(documents), batch_size):
        batch = documents[i:i+batch_size]
        points = []
        
        for idx, doc in enumerate(batch):
            vector = embed_text(doc)
            points.append(PointStruct(
                id=str(i + idx),  # Ensure unique IDs across batches
                vector=vector,
                payload={"text": doc}
            ))
        
        client.upsert(
            collection_name=collection_name,
            points=points
        )
        
        total_inserted += len(points)
        print(f"Inserted batch {i//batch_size + 1}, total: {total_inserted} documents")
    
    return total_inserted

# Example usage of batch processing (commented out to avoid re-inserting documents)
# large_document_set = [f"Document {i}" for i in range(100)]
# batch_insert_documents(large_document_set, batch_size=20)

# 11. Cleanup (Optional)
def cleanup():
    """Delete the collection."""
    client.delete_collection(collection_name=collection_name)
    print(f"Collection '{collection_name}' deleted")

# Run the test if this script is executed directly
if __name__ == "__main__":
    test_rag_pipeline()
    
    # Uncomment to clean up
    # cleanup()
    
    print("\nDone! Check the HoneyHive UI to see the traces.")
    print("Navigate to your project in the HoneyHive dashboard and click on the 'Data Store' or 'Traces' tab.") 