from openai import OpenAI
from pinecone import Pinecone

# add init
from honeyhive.tracer import HoneyHiveTracer

HoneyHiveTracer.init(
    api_key=os.environ["HH_API_KEY"],
    project="New Project",
    source="dev",
    session_name="RAG Session"
)

openai_client = OpenAI()
pc = Pinecone()
index = pc.Index("chunk-size-512")

def main():
    query = "What does the document talk about?"

    # Embed query
    res = openai_client.embeddings.create(
        model="text-embedding-ada-002",
        input=query
    )
    query_vector = res.data[0].embedding

    # Get relevant documents
    res = index.query(vector=query_vector, top_k=3, include_metadata=True)
    docs = [item['metadata']['_node_content'] for item in res['matches']]

    # Generate response
    context = "\n".join(docs)
    prompt = f"Context: {context}\n\nQuestion: {query}\n\nAnswer:"
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ]
    )
    response_text = response.choices[0].message.content

    print(f"Query: {query}")
    print(f"Response: {response_text}")

if __name__ == "__main__":
    main()
