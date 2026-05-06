"""
Qdrant RAG Integration with HoneyHive

Demonstrates a Retrieval-Augmented Generation (RAG) pipeline using:
- Qdrant as the vector store
- OpenAI for embeddings and chat completions
- HoneyHive for observability and tracing
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

# Initialize clients
openai_client = OpenAI()
qdrant_client = QdrantClient(url=os.getenv("QDRANT_URL", "http://localhost:6333"))

COLLECTION_NAME = "documents"
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536

# Sample documents
DOCUMENTS = [
    "Qdrant is a vector database optimized for storing and searching high-dimensional vectors.",
    "HoneyHive provides observability for AI applications, including RAG pipelines.",
    "Retrieval-Augmented Generation (RAG) combines retrieval systems with generative models.",
    "Vector databases like Qdrant are essential for efficient similarity search in RAG systems.",
    "OpenAI's embedding models convert text into high-dimensional vectors for semantic search.",
]


@trace
def embed_text(text: str) -> list:
    """Generate embeddings using OpenAI."""
    response = openai_client.embeddings.create(model=EMBEDDING_MODEL, input=text)
    return response.data[0].embedding


@trace
def setup_collection():
    """Create collection and insert documents."""
    if qdrant_client.collection_exists(COLLECTION_NAME):
        qdrant_client.delete_collection(COLLECTION_NAME)

    qdrant_client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
    )

    points = [
        PointStruct(id=idx, vector=embed_text(doc), payload={"text": doc})
        for idx, doc in enumerate(DOCUMENTS)
    ]
    qdrant_client.upsert(collection_name=COLLECTION_NAME, points=points)
    return len(points)


@trace
def retrieve(query: str, top_k: int = 3) -> list:
    """Retrieve relevant documents for a query."""
    q_vector = embed_text(query)
    results = qdrant_client.query_points(
        collection_name=COLLECTION_NAME,
        query=q_vector,
        limit=top_k,
        with_payload=True,
    )
    return [
        {"text": pt.payload["text"], "score": pt.score}
        for pt in results.points
    ]


@trace
def rag_query(query: str) -> dict:
    """End-to-end RAG: retrieve context, then generate an answer."""
    docs = retrieve(query)

    context = "\n".join(
        f"- {doc['text']} (score: {doc['score']:.4f})" for doc in docs
    )

    completion = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Answer based on the provided context."},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"},
        ],
        temperature=0.3,
    )

    return {
        "query": query,
        "answer": completion.choices[0].message.content,
        "retrieved_documents": docs,
    }


if __name__ == "__main__":
    num = setup_collection()
    print(f"Inserted {num} documents into Qdrant\n")

    for q in ["What is Qdrant used for?", "How does HoneyHive help with RAG pipelines?"]:
        result = rag_query(q)
        print(f"Q: {result['query']}")
        print(f"A: {result['answer']}\n")

    print("Done! Check the HoneyHive UI to see the traces.")
