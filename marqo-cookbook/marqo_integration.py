"""
HoneyHive Integration with Marqo Vector Database

This example demonstrates how to integrate HoneyHive tracing with Marqo vector database
in a simple RAG (Retrieval Augmented Generation) application.
"""

# Add virtual environment path to sys.path at the beginning
import sys
import os
import marqo
import requests
from openai import OpenAI
from honeyhive import HoneyHiveTracer, trace

# Set your API keys
HONEYHIVE_API_KEY = "your honeyhive api key"
OPENAI_API_KEY = "your openai api key"

# NOTE: Marqo server needs to be running locally on port 8882, or you need to set MARQO_URL
# environment variable to point to your Marqo server
# For local development, you can run Marqo in Docker with:
# docker run -p 8882:8882 marqoai/marqo:latest
MARQO_URL = os.environ.get("MARQO_URL", "http://localhost:8882")  # Default Marqo URL

# Initialize OpenAI client
openai_api_key = OPENAI_API_KEY

openai_client = OpenAI(api_key=openai_api_key)
# Initialize HoneyHive tracer
HoneyHiveTracer.init(
    api_key=HONEYHIVE_API_KEY,
    project="your project name",
    source="dev",
)

# Check if Marqo server is available
def is_marqo_available():
    try:
        response = requests.get(f"{MARQO_URL}/health", timeout=2)
        return response.status_code == 200
    except requests.RequestException:
        return False

# If Marqo server is not available, print a warning
marqo_available = is_marqo_available()
if not marqo_available:
    print(f"""
WARNING: Marqo server is not available at {MARQO_URL}
To run this example properly, you need to start a Marqo server:
    docker run -p 8882:8882 marqoai/marqo:latest
Or set the MARQO_URL environment variable to point to a running Marqo server.
Continuing with mock functionality for demonstration purposes.
""")

# Initialize Marqo client if server is available
if marqo_available:
    client = marqo.Client(url=MARQO_URL)
else:
    # Create a mock client for demonstration
    client = None

# Define the index name
INDEX_NAME = "honeyhive_marqo_demo"

@trace
def create_marqo_index():
    """Create a Marqo index if it doesn't exist."""
    if not marqo_available:
        print("[MOCK] Creating index (simulated)")
        return
        
    try:
        # Check if index exists
        indexes = client.get_indexes()
        if INDEX_NAME not in [index["indexName"] for index in indexes.get("results", [])]:
            # Create the index with simpler settings based on documentation
            client.create_index(INDEX_NAME, model="hf/e5-base-v2")
            print(f"Created index: {INDEX_NAME}")
        else:
            print(f"Index {INDEX_NAME} already exists")
    except Exception as e:
        print(f"Error creating index: {e}")
        raise

@trace
def add_documents_to_marqo(documents):
    """Add documents to the Marqo index."""
    if not marqo_available:
        print(f"[MOCK] Adding {len(documents)} documents to index (simulated)")
        return
        
    try:
        # Add documents to the index following the documentation's format
        client.index(INDEX_NAME).add_documents(
            documents=documents,
            tensor_fields=["text"]  # Specify which fields to vectorize
        )
        print(f"Added {len(documents)} documents to index")
    except Exception as e:
        print(f"Error adding documents: {e}")
        raise

@trace
def search_marqo(query, limit=3):
    """Search the Marqo index for relevant documents."""
    if not marqo_available:
        print(f"[MOCK] Searching for: {query} (simulated)")
        # Return mock results for demonstration
        mock_hits = [
            {"text": "HoneyHive provides tracing and monitoring for AI applications.", "_id": "2", "score": 0.95},
            {"text": "Retrieval Augmented Generation (RAG) combines retrieval systems with generative models.", "_id": "3", "score": 0.85},
            {"text": "Vector databases store embeddings which are numerical representations of data.", "_id": "4", "score": 0.75}
        ]
        return mock_hits
        
    try:
        # Search the index
        results = client.index(INDEX_NAME).search(
            q=query,
            limit=limit
        )
        print(f"Found {len(results['hits'])} results for query: {query}")
        return results["hits"]
    except Exception as e:
        print(f"Error searching index: {e}")
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
        response = openai_client.chat.completions.create(
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
    Run the complete RAG pipeline with Marqo and HoneyHive tracing.
    
    Args:
        query: The user query
        documents: Optional list of documents to add to the index
    
    Returns:
        The generated response
    """
    # Create index if needed
    create_marqo_index()
    
    # Add documents if provided
    if documents:
        add_documents_to_marqo(documents)
    
    # Search for relevant documents
    results = search_marqo(query)
    
    # Generate response
    response = generate_response(query, results)
    
    return response

def main():
    # Sample documents
    documents = [
        {"text": "Marqo is a tensor search engine that makes it easy to build search into your applications.", "_id": "1"},
        {"text": "HoneyHive provides tracing and monitoring for AI applications.", "_id": "2"},
        {"text": "Retrieval Augmented Generation (RAG) combines retrieval systems with generative models.", "_id": "3"},
        {"text": "Vector databases store embeddings which are numerical representations of data.", "_id": "4"},
        {"text": "OpenTelemetry is an observability framework for cloud-native software.", "_id": "5"}
    ]
    
    # Sample query
    query = "How can HoneyHive help with RAG applications?"
    
    # Run the RAG pipeline
    response = rag_pipeline(query, documents)
    
    print("\n=== Generated Response ===")
    print(response)

if __name__ == "__main__":
    main()
