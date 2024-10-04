// Import necessary modules
import * as fs from 'fs';
import { OpenAI } from "@langchain/openai";
import { TextLoader } from 'langchain/document_loaders/fs/text';
import { RecursiveCharacterTextSplitter } from 'langchain/text_splitter';
import { OpenAIEmbeddings } from "@langchain/openai";
import { FaissStore } from "@langchain/community/vectorstores/faiss";
import { RetrievalQAChain } from 'langchain/chains';
import { HoneyHiveLangChainTracer } from 'honeyhive';

// Async function to run the QA system
async function runQA() {
  const tracer = new HoneyHiveLangChainTracer({
    project: process.env.HH_PROJECT,
    sessionName: 'langchain-js-sotu-rag',
    apiKey: process.env.HH_API_KEY,
  });

  // Load the document
  const loader = new TextLoader('state_of_the_union.txt');
  const documents = await loader.load();

  // Split the document into chunks
  const textSplitter = new RecursiveCharacterTextSplitter({
    chunkSize: 1000,
    chunkOverlap: 200,
  });
  const docs = await textSplitter.splitDocuments(documents);

  // Create embeddings
  const embeddings = new OpenAIEmbeddings();

  // Create a FAISS vector store from the documents
  const vectorStore = await FaissStore.fromDocuments(docs, embeddings);

  // Create a retriever interface
  const retriever = vectorStore.asRetriever();

  // Initialize the OpenAI LLM
  const llm = new OpenAI({ temperature: 0 });

  // Create a RetrievalQA chain
  const qaChain = RetrievalQAChain.fromLLM(llm, retriever);

  // Ask a question
  const query = "What did the president say about Ketanji Brown Jackson?";
  const res = await qaChain.call({ query, callbacks: [tracer] });

  console.log(res.text);
}

// Run the QA system
runQA();
