import os
from openai import OpenAI
from pinecone import Pinecone

from honeyhive.tracer import HoneyHiveTracer
from honeyhive.tracer.custom import trace

# Set up environment variables
# os.environ["OPENAI_API_KEY"] = "your-openai-api-key"
# os.environ["PINECONE_API_KEY"] = "your-pinecone-api-key"

# Initialize HoneyHive Tracer
HoneyHiveTracer.init(
    api_key="your-honeyhive-api-key",
    project="your-honeyhive-project-name",
    source="dev",
    session_name="RAG Session"
)

# Initialize clients
openai_client = OpenAI()
pc = Pinecone()
index = pc.Index("your-index-name")

def embed_query(query):
    res = openai_client.embeddings.create(
        model="text-embedding-ada-002",
        input=query
    )
    query_vector = res.data[0].embedding
    return query_vector

@trace(
    config={
        "embedding_model": "text-embedding-ada-002",
        "top_k": 3
    }
)
def get_relevant_documents(query):
    query_vector = embed_query(query)
    res = index.query(vector=query_vector, top_k=3, include_metadata=True)
    return [item['metadata']['_node_content'] for item in res['matches']]

@trace(
    config={
        "model": "gpt-4o",
        "prompt": "You are a helpful assistant" 
    },
    metadata={
        "version": 1
    }
)
def generate_response(context, query):
    prompt = f"Context: {context}\n\nQuestion: {query}\n\nAnswer:"
    response = openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content

@trace()
def rag_pipeline(query):
    docs = get_relevant_documents(query)
    response = generate_response("\n".join(docs), query)
    return response

def main():
    query = "What does the document talk about?"
    response = rag_pipeline(query)
    print(f"Query: {query}")
    print(f"Response: {response}")
    
    HoneyHiveTracer.set_metadata({
        "experiment-id": 123
    })
    
    # Simulate getting user feedback
    user_rating = 4
    HoneyHiveTracer.set_feedback({
        "rating": user_rating,
        "comment": "The response was accurate and helpful."
    })

if __name__ == "__main__":
    main()
