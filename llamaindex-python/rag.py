import os
from llama_index.core import (
    GPTVectorStoreIndex,
    SimpleDirectoryReader,
    Settings
)
from llama_index.core.retrievers import VectorIndexRetriever
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai import OpenAI
from honeyhive import HoneyHiveTracer

# Initialize HoneyHiveTracer
HoneyHiveTracer.init(api_key=os.environ["HH_API_KEY"], project=os.environ["HH_PROJECT"])

# Load the document
documents = SimpleDirectoryReader(input_files=['state_of_the_union.txt']).load_data()

# Initialize the OpenAI LLM using LlamaIndex's OpenAI wrapper
llm = OpenAI(temperature=0)

# Create the embedding model
embedding_model = OpenAIEmbedding()

# Add the LLM predictor and embedding model to the Settings object
Settings.llm = llm
Settings.embed_model = embedding_model

# Create a vector index from the documents
index = GPTVectorStoreIndex.from_documents(
    documents,
)

# Ask a question
query = "What did the president say about Ketanji Brown Jackson?"
retriever = VectorIndexRetriever(index=index)
query_engine = RetrieverQueryEngine.from_args(retriever)
response = query_engine.query(query)

print(response)
