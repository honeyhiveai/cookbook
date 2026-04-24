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

import os

from dotenv import load_dotenv
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from honeyhive import HoneyHiveTracer, trace
from openinference.instrumentation.openai import OpenAIInstrumentor

load_dotenv(override=True)

# Initialize HoneyHive tracer and OpenAI auto-instrumentation
tracer = HoneyHiveTracer.init(
    api_key=os.getenv("HH_API_KEY"),
    project=os.getenv("HH_PROJECT", "qdrant-rag-example"),
    session_name="qdrant-integration-demo",
)
OpenAIInstrumentor().instrument(tracer_provider=tracer.provider)

# Initialize OpenAI client
openai_client = OpenAI()

# 2. Connect to Qdrant
# Option 1: Self-Hosted Qdrant (Local)
# docker pull qdrant/qdrant
# docker run -p 6333:6333 -p 6334:6334 -v "$(pwd)/qdrant_storage:/qdrant/storage" qdrant/qdrant

client = QdrantClient(url="http://localhost:6333")
print("Connected to local Qdrant instance")

# Option 2: Qdrant Cloud (uncomment to use)
# QDRANT_HOST = "your-cluster-id.eu-central.aws.cloud.qdrant.io"
# QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
# client = QdrantClient(host=QDRANT_HOST, api_key=QDRANT_API_KEY)

# 3. Create a Collection
collection_name = "documents"

if not client.collection_exists(collection_name):
    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=1536, distance=Distance.COSINE)
    )
    print(f"Collection '{collection_name}' created")
else:
    print(f"Collection '{collection_name}' already exists")

# 4. Define Embedding Function
@trace
def embed_text(text: str) -> list:
    """Generate embeddings for a text using OpenAI's API."""
    response = openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
    )
    return response.data[0].embedding

# 5. Insert Documents into Qdrant
documents = [
    "Qdrant is a vector database optimized for storing and searching high-dimensional vectors.",
    "HoneyHive provides observability for AI applications, including RAG pipelines.",
    "Retrieval-Augmented Generation (RAG) combines retrieval systems with generative models.",
    "Vector databases like Qdrant are essential for efficient similarity search in RAG systems.",
    "OpenAI's embedding models convert text into high-dimensional vectors for semantic search."
]

@trace
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

    client.upsert(
        collection_name=collection_name,
        points=points
    )
    return len(points)

num_inserted = insert_documents(documents)
print(f"Inserted {num_inserted} documents into Qdrant")

# 6. Define Retrieval Function
@trace
def get_relevant_docs(query: str, top_k: int = 3) -> list:
    """Retrieve relevant documents for a query."""
    q_vector = embed_text(query)

    search_results = client.search(
        collection_name=collection_name,
        query_vector=q_vector,
        limit=top_k,
        with_payload=True,
    )

    docs = []
    for point in search_results:
        docs.append({
            "text": point.payload.get("text"),
            "score": point.score,
        })

    return docs

# 7. Define Answer Generation Function
@trace
def answer_query(query: str) -> str:
    """Generate an answer for a query using retrieved documents."""
    relevant_docs = get_relevant_docs(query)

    context = "\n\n".join([f"Document {i+1} (Score: {doc['score']:.4f}):\n{doc['text']}"
                          for i, doc in enumerate(relevant_docs)])

    prompt = f"""Answer the question based on the following context:

Context:
{context}

Question: {query}

Answer:"""

    completion = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that answers questions based on the provided context."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
    )

    return completion.choices[0].message.content

# 8. Complete RAG Pipeline
@trace
def rag_pipeline(query: str) -> dict:
    """End-to-end RAG pipeline."""
    relevant_docs = get_relevant_docs(query)
    answer = answer_query(query)

    return {
        "query": query,
        "answer": answer,
        "retrieved_documents": relevant_docs
    }

# 9. Test the RAG Pipeline
def test_rag_pipeline():
    query1 = "What is Qdrant used for?"
    result1 = rag_pipeline(query1)

    print(f"Query: {result1['query']}")
    print(f"Answer: {result1['answer']}")
    print("\nRetrieved Documents:")
    for i, doc in enumerate(result1['retrieved_documents']):
        print(f"Document {i+1} (Score: {doc['score']:.4f}): {doc['text']}")

    query2 = "How does HoneyHive help with RAG pipelines?"
    result2 = rag_pipeline(query2)

    print(f"\nQuery: {result2['query']}")
    print(f"Answer: {result2['answer']}")
    print("\nRetrieved Documents:")
    for i, doc in enumerate(result2['retrieved_documents']):
        print(f"Document {i+1} (Score: {doc['score']:.4f}): {doc['text']}")

# 10. Advanced: Batch Processing
@trace
def batch_insert_documents(documents, batch_size=10):
    """Insert documents in batches."""
    total_inserted = 0

    for i in range(0, len(documents), batch_size):
        batch = documents[i:i+batch_size]
        points = []

        for idx, doc in enumerate(batch):
            vector = embed_text(doc)
            points.append(PointStruct(
                id=str(i + idx),
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

# 11. Cleanup (Optional)
def cleanup():
    """Delete the collection."""
    client.delete_collection(collection_name=collection_name)
    print(f"Collection '{collection_name}' deleted")

if __name__ == "__main__":
    test_rag_pipeline()
    # cleanup()
    print("\nDone! Check the HoneyHive UI to see the traces.")
