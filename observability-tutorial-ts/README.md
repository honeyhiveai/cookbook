# Observability Tutorial (TypeScript)

This directory contains a TypeScript script demonstrating how to implement observability in a RAG (Retrieval-Augmented Generation) pipeline using OpenAI, Pinecone, and HoneyHive for tracing and evaluation.

## Prerequisites

- Node.js (version compatible with TypeScript 5.0+)
- OpenAI API key
- Pinecone API key
- HoneyHive API key
- Pinecone index set up

## Setup

1. Clone this repository:
   ```
   git clone https://github.com/honeyhiveai/cookbook
   cd observability-tutorial-ts
   ```

2. Install the required packages:
   ```
   npm install
   ```

3. Create a `.env` file in the project root and add your API keys:
   ```
   OPENAI_API_KEY=your-openai-api-key
   PINECONE_API_KEY=your-pinecone-api-key
   HH_API_KEY=your-honeyhive-api-key
   HH_PROJECT=your-honeyhive-project-name
   ```

4. Update the Pinecone index name in `tutorial.ts`:
   - Replace `"your-index-name"` with your Pinecone index name

## Usage

Run the script:
```
npm start
```

## Docker Support (Optional)

If you prefer to use Docker, follow these steps:

1. Build the Docker image:
   ```
   docker build -t observability-tutorial-ts .
   ```

2. Run the Docker container:
   ```
   docker run --env-file .env observability-tutorial-ts
   ```

This will run the application inside a Docker container, using the environment variables from your `.env` file.

## How It Works

This script demonstrates a RAG pipeline with observability using HoneyHive. Here's a breakdown of what the script does:

1. Imports necessary libraries and sets up API clients
2. Initializes HoneyHive Tracer for observability
3. Defines functions for embedding queries, retrieving relevant documents, and generating responses
4. Implements a RAG pipeline that combines document retrieval and response generation
5. Uses HoneyHive's `traceFunction` to log function calls and their metadata
6. Simulates user feedback and logs it using HoneyHive

The script uses OpenAI's API for embeddings and text generation, Pinecone for vector search, and HoneyHive for tracing and observability.

## File Structure

- `tutorial.ts`: The main TypeScript script demonstrating the RAG pipeline with observability
- `package.json`: Node.js package configuration file
- `README.md`: This file, containing instructions and explanations
- `.env`: File for storing environment variables (not included in repository)
- `Dockerfile`: Configuration file for building a Docker image (if using Docker)

## Notes

- Ensure you keep your API keys confidential and do not commit them to version control.
- The script uses OpenAI's "text-embedding-ada-002" for embeddings and "gpt-4" for text generation. Adjust these if needed.
- The Pinecone index should be set up beforehand with appropriate data for the RAG pipeline to work effectively.
- Observability data will be available in your HoneyHive project for analysis and evaluation.
- This project uses TypeScript and requires `tsx` for execution. Make sure your Node.js version is compatible with the TypeScript version specified in `package.json`.

## Dependencies

The main dependencies for this project are:

- `@pinecone-database/pinecone`: For vector database operations
- `openai`: For OpenAI API interactions
- `dotenv`: For loading environment variables
- `honeyhive`: For observability and tracing

Dev dependencies include TypeScript and related tools for running TypeScript code.