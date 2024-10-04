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

  // Load the document with tracing
  const loader = new TextLoader('state_of_the_union.txt', {
    callbacks: [tracer], // Tracing document loading
  });
  const documents = await loader.load();

  // Split the document into chunks with tracing
  const textSplitter = new RecursiveCharacterTextSplitter({
    chunkSize: 1000,
    chunkOverlap: 200,
    callbacks: [tracer], // Tracing text splitting
  });
  const docs = await textSplitter.splitDocuments(documents);

  // Create embeddings with tracing
  const embeddings = new OpenAIEmbeddings({
    callbacks: [tracer], // Tracing embedding creation
  });

  // Create a FAISS vector store from the documents with tracing
  const vectorStore = await FaissStore.fromDocuments(docs, embeddings, {
    callbacks: [tracer], // Tracing vector store creation
  });

  // Create a retriever interface with tracing
  const retriever = vectorStore.asRetriever({
    callbacks: [tracer], // Tracing retrieval
  });

  // Initialize the OpenAI LLM with tracing
  const llm = new OpenAI({
    temperature: 0,
    callbacks: [tracer], // Tracing LLM calls
  });

  // Create a RetrievalQA chain with tracing
  const qaChain = RetrievalQAChain.fromLLM(llm, retriever, {
    callbacks: [tracer], // Tracing the QA chain
  });

  // Ask a question
  const query = "What did the president say about Ketanji Brown Jackson?";
  const res = await qaChain.call({ query, callbacks: [tracer] });

  console.log(res.text);
}

// Run the QA system
runQA();
