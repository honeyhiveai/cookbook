import os
from langchain.document_loaders import TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores import FAISS
from langchain.embeddings import OpenAIEmbeddings
from langchain.chains import RetrievalQA
from langchain.llms import OpenAI

# Load the document
loader = TextLoader('state_of_the_union.txt')
documents = loader.load()

# Split the document into chunks
text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
docs = text_splitter.split_documents(documents)

# Create embeddings
embeddings = OpenAIEmbeddings()

# Create a FAISS vector store from the documents
vectorstore = FAISS.from_documents(docs, embeddings)

# Create a retriever interface
retriever = vectorstore.as_retriever()

# Initialize the OpenAI LLM
llm = OpenAI(temperature=0)

# Create a RetrievalQA chain
qa_chain = RetrievalQA.from_chain_type(
    llm=llm,
    chain_type="stuff",
    retriever=retriever
)

# Ask a question
query = "What did the president say about Ketanji Brown Jackson?"
result = qa_chain.run(query)

print(result)
