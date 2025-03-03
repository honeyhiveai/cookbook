"""
# Mistral AI Integration with HoneyHive

This script demonstrates how to integrate Mistral AI with HoneyHive for observability
in Large Language Model (LLM) applications.

## Overview

Mistral AI is a model provider offering cutting-edge large language models, including
the open-source Mistral 7B model. Mistral provides a cloud API that allows you to use
their models for inference without hosting them yourself.

This script covers:
1. Setting up authentication with Mistral AI
2. Making inference calls to Mistral's models
3. Integrating with HoneyHive for observability
4. Building applications with Mistral's chat completion and embedding capabilities
"""

# 1. Installation and Setup
# First, install the required packages:
# pip install mistralai==0.2.0 honeyhive

# Import Libraries
from mistralai.client import MistralClient
from mistralai.models.chat_completion import ChatMessage
import os
import numpy as np
from honeyhive.tracer import HoneyHiveTracer
from honeyhive.tracer.custom import trace  # for custom span annotation

# Set API Keys
mistral_api_key = os.getenv("MISTRAL_API_KEY", "your_mistral_api_key")

# Initialize HoneyHive Tracer
HoneyHiveTracer.init(
    api_key=os.getenv("HONEYHIVE_API_KEY", "your_honeyhive_api_key"),
    project="mistral-integration-example",  # Your project name in HoneyHive
    session_name="mistral-integration-demo"  # Optional session identifier
)

# 2. Initialize Mistral Client
client = MistralClient(api_key=mistral_api_key)
print("Mistral client initialized")

# 3. Basic Chat Completion
@trace(config={"model": "mistral-small-latest"})
def simple_chat_completion(prompt: str):
    """Simple chat completion with Mistral AI."""
    response = client.chat(
        model="mistral-small-latest",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

# Test with a simple prompt
prompt = "What is your name and model type? Answer in one short sentence."
response = simple_chat_completion(prompt)

print("User:", prompt)
print("Mistral:", response)

# 4. Multi-Turn Conversation
@trace(config={"model": "mistral-small-latest", "conversation_type": "multi_turn"})
def multi_turn_conversation(messages):
    """Multi-turn conversation with Mistral AI."""
    response = client.chat(
        model="mistral-small-latest",
        messages=messages
    )
    return response.choices[0].message

# Create a conversation
conversation = [
    {"role": "user", "content": "Hello, I'd like to learn about vector databases."},
    {"role": "assistant", "content": "Hi there! I'd be happy to help you learn about vector databases. Vector databases are specialized database systems designed to store and query high-dimensional vectors efficiently. These vectors often represent embeddings of data like text, images, or audio. What specific aspects of vector databases would you like to know about?"},
    {"role": "user", "content": "What are the most popular vector databases used with RAG systems?"}
]

# Get response
response = multi_turn_conversation(conversation)

# Print the conversation
for message in conversation:
    print(f"{message['role'].capitalize()}: {message['content']}")
print(f"Assistant: {response.content}")

# 5. Streaming Responses
@trace(config={"model": "mistral-small-latest", "streaming": True})
def stream_chat_completion(prompt: str):
    """Stream chat completion with Mistral AI."""
    stream = client.chat_stream(
        model="mistral-small-latest",
        messages=[{"role": "user", "content": prompt}]
    )
    
    # Collect the tokens
    full_response = ""
    print("Streaming response:")
    for chunk in stream:
        content = chunk.choices[0].delta.content
        if content:
            print(content, end="", flush=True)
            full_response += content
    print("\n\nFull response collected:", full_response)
    return full_response

# Test with a prompt that requires a longer response
prompt = "Explain the concept of Retrieval-Augmented Generation (RAG) in 3-4 sentences."
response = stream_chat_completion(prompt)

# 6. Using Different Models
@trace(config={"model_comparison": True})
def compare_models(prompt: str):
    """Compare responses from different Mistral models."""
    models = ["mistral-small-latest", "mistral-medium-latest"]  # Add "mistral-large-latest" if available
    results = {}
    
    for model in models:
        try:
            with trace(config={"model": model}):
                response = client.chat(
                    model=model,
                    messages=[{"role": "user", "content": prompt}]
                )
                results[model] = response.choices[0].message.content
        except Exception as e:
            results[model] = f"Error: {str(e)}"
    
    return results

# Test with a complex prompt
prompt = "What are the key differences between traditional search and vector search? Provide a concise explanation."
model_responses = compare_models(prompt)

# Print responses from each model
for model, response in model_responses.items():
    print(f"\n--- {model} ---")
    print(response)

# 7. Generating Embeddings
@trace(config={"model": "mistral-embed"})
def generate_embeddings(texts):
    """Generate embeddings for a list of texts using Mistral's embedding model."""
    response = client.embeddings(
        model="mistral-embed",
        input=texts
    )
    
    # Extract embeddings from response
    embeddings = [data.embedding for data in response.data]
    return embeddings

# Test with some sample texts
texts = [
    "Retrieval-Augmented Generation combines search with generative AI.",
    "Vector databases store and query high-dimensional embeddings efficiently.",
    "HoneyHive provides observability for AI applications."
]

embeddings = generate_embeddings(texts)

# Print embedding dimensions and a sample of values
for i, embedding in enumerate(embeddings):
    print(f"Text {i+1} embedding: dimension={len(embedding)}, sample={embedding[:5]}...")

# 8. Building a Simple RAG System with Mistral
# Simple vector store implementation
class SimpleVectorStore:
    def __init__(self):
        self.documents = []
        self.embeddings = []
    
    def add_documents(self, documents, embeddings):
        self.documents.extend(documents)
        if not self.embeddings:
            self.embeddings = embeddings
        else:
            self.embeddings = np.vstack([self.embeddings, embeddings])
    
    def search(self, query_embedding, top_k=3):
        if not self.embeddings or len(self.embeddings) == 0:
            return []
        
        # Convert query_embedding to numpy array and reshape
        query_embedding = np.array(query_embedding).reshape(1, -1)
        
        # Calculate cosine similarity
        similarities = np.dot(query_embedding, np.array(self.embeddings).T)[0]
        
        # Get top-k indices
        top_indices = np.argsort(similarities)[-top_k:][::-1]
        
        # Return documents and scores
        results = []
        for idx in top_indices:
            results.append({
                "document": self.documents[idx],
                "score": similarities[idx]
            })
        
        return results

# Sample documents for our knowledge base
documents = [
    "Mistral AI is a company that develops large language models, including the open-source Mistral 7B model.",
    "Mistral's models are known for their strong performance relative to their size, with the 7B model outperforming many larger models.",
    "Mistral provides a cloud API that allows developers to use their models without hosting them.",
    "HoneyHive is an observability platform for AI applications, helping developers monitor and debug their AI systems.",
    "HoneyHive can trace API calls to various model providers, including Mistral, OpenAI, Anthropic, and others.",
    "Retrieval-Augmented Generation (RAG) is a technique that combines retrieval systems with generative models.",
    "In RAG, relevant documents are retrieved from a knowledge base and provided as context to a language model.",
    "Vector databases are essential for efficient similarity search in RAG systems, storing document embeddings.",
    "Mistral's embedding model can be used to convert text into vector representations for semantic search."
]

# Create a simple vector store
vector_store = SimpleVectorStore()

# Generate embeddings for documents and add to vector store
document_embeddings = generate_embeddings(documents)
vector_store.add_documents(documents, document_embeddings)

print(f"Added {len(documents)} documents to the vector store")

@trace(config={"system": "rag", "components": ["mistral-embed", "vector-store", "mistral-small-latest"]})
def mistral_rag(query, top_k=3):
    """Simple RAG system using Mistral for embeddings and generation."""
    # 1. Generate embedding for the query
    with trace(config={"step": "embedding"}):
        query_embedding = generate_embeddings([query])[0]
    
    # 2. Retrieve relevant documents
    with trace(config={"step": "retrieval", "top_k": top_k}):
        results = vector_store.search(query_embedding, top_k=top_k)
        context = "\n\n".join([f"Document {i+1} (Score: {result['score']:.4f}):\n{result['document']}" 
                              for i, result in enumerate(results)])
    
    # 3. Generate answer using Mistral
    with trace(config={"step": "generation", "model": "mistral-small-latest"}):
        prompt = f"""Answer the question based on the following context:

Context:
{context}

Question: {query}

Answer:"""
        
        response = client.chat(
            model="mistral-small-latest",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that answers questions based on the provided context."},
                {"role": "user", "content": prompt}
            ]
        )
        
        answer = response.choices[0].message.content
    
    return {
        "query": query,
        "answer": answer,
        "retrieved_documents": results
    }

# Test the RAG system
def test_rag_system():
    query = "What is Mistral AI and how does it relate to RAG systems?"
    result = mistral_rag(query)
    
    print(f"Query: {result['query']}")
    print(f"\nAnswer: {result['answer']}")
    print("\nRetrieved Documents:")
    for i, doc in enumerate(result['retrieved_documents']):
        print(f"Document {i+1} (Score: {doc['score']:.4f}): {doc['document']}")

# 9. Advanced: Model Parameters
@trace(config={"model": "mistral-small-latest", "parameter_tuning": True})
def test_model_parameters(prompt, temperature, max_tokens):
    """Test different model parameters."""
    response = client.chat(
        model="mistral-small-latest",
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=max_tokens
    )
    return response.choices[0].message.content

def compare_parameters():
    # Test with different parameters
    prompt = "Write a short poem about artificial intelligence."
    
    print("--- Low Temperature (0.3) ---")
    response_low_temp = test_model_parameters(prompt, temperature=0.3, max_tokens=100)
    print(response_low_temp)
    
    print("\n--- High Temperature (0.9) ---")
    response_high_temp = test_model_parameters(prompt, temperature=0.9, max_tokens=100)
    print(response_high_temp)

# Run the tests if this script is executed directly
if __name__ == "__main__":
    # Uncomment to run the RAG system test
    test_rag_system()
    
    # Uncomment to compare different model parameters
    # compare_parameters()
    
    print("\nDone! Check the HoneyHive UI to see the traces.")
    print("Navigate to your project in the HoneyHive dashboard and click on the 'Data Store' or 'Traces' tab.") 