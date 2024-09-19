from openai import OpenAI
from pinecone import Pinecone

# Initialize clients
openai_client = OpenAI()
pc = Pinecone()
index = pc.Index("chunk-size-512")

def embed_query(query):
    res = openai_client.embeddings.create(
        model="text-embedding-ada-002",
        input=query
    )
    query_vector = res.data[0].embedding
    return query_vector

def get_relevant_documents(query):
    query_vector = embed_query(query)
    res = index.query(vector=query_vector, top_k=3, include_metadata=True)
    return [item['metadata']['_node_content'] for item in res['matches']]

def generate_response(context, query):
    prompt = f"Context: {context}\n\nQuestion: {query}\n\nAnswer:"
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content

def rag_pipeline(query):
    docs = get_relevant_documents(query)
    response = generate_response("\n".join(docs), query)
    return response 

def main():
    query = "What does the document talk about?"
    response = rag_pipeline(query)
    print(f"Query: {query}")
    print(f"Response: {response}")

if __name__ == "__main__":
    main()
