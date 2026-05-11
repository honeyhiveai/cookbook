"""
HoneyHive Integration with Chroma Vector Database

This example demonstrates how to integrate HoneyHive tracing with Chroma vector database
in a simple RAG (Retrieval Augmented Generation) application.
"""

import os
import chromadb
from openai import OpenAI
from honeyhive import HoneyHiveTracer, trace

# Set your API keys
HONEYHIVE_API_KEY = "your honeyhive api key"
OPENAI_API_KEY = "your openai api key"

client = OpenAI(api_key=OPENAI_API_KEY)
# Initialize OpenAI client
# Initialize HoneyHive tracer
HoneyHiveTracer.init(
    api_key=HONEYHIVE_API_KEY,
    project="multi-test",
    source="dev",
    session_name="chroma_rag_example"
)

# Initialize Chroma client
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
