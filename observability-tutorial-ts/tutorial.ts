import * as dotenv from 'dotenv';
import { OpenAI } from 'openai';
import { Pinecone } from '@pinecone-database/pinecone';
import { HoneyHiveTracer } from "honeyhive";

// Initialize the HoneyHive tracer at the start
const tracer = await HoneyHiveTracer.init({
    apiKey: process.env.HH_API_KEY,
    project: process.env.HH_PROJECT,
    source: "dev", // e.g. "prod", "dev", etc.
    sessionName: "RAG Session",
});

// Initialize clients
const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
const pc = new Pinecone({ apiKey: process.env.PINECONE_API_KEY });
const index = pc.index("your-index-name");

const embedQuery = async (query) => {
    const embeddingResponse = await openai.embeddings.create({
        model: "text-embedding-ada-002",
        input: query
    });
    return embeddingResponse.data[0].embedding;
};

const getRelevantDocumentsConfig = {
    "embedding_model": "text-embedding-ada-002",
    "top_k": 3
};

// Decorate the intermediate steps
const getRelevantDocuments = tracer.traceFunction(getRelevantDocumentsConfig)(
    async function getRelevantDocuments(queryVector) {
        const queryResult = await index.query({
            vector: queryVector,
            topK: 3,
            includeMetadata: true
        });
        
        return queryResult.matches.map(item => item.metadata!._node_content as string);
    }
);

const generateResponseConfig = {
    "model": "gpt-4o",
    "prompt": "You are a helpful assistant" 
};
const generateResponseMetadata = {
    "version": 1
};

// Decorate the intermediate steps
const generateResponse = tracer.traceFunction(generateResponseConfig, generateResponseMetadata)(
    async function generateResponse(context, query) {
        const prompt = `Context: ${context}\n\nQuestion: ${query}\n\nAnswer:`;
        const completion = await openai.chat.completions.create({
            model: "gpt-4",
            messages: [
                { role: "system", content: "You are a helpful assistant." },
                { role: "user", content: prompt }
            ]
        });
        return completion.choices[0].message.content || "";
    }
);

// Decorate the main application logic
const ragPipeline = tracer.traceFunction()(
    async function ragPipeline(query) {
        const queryVector = await embedQuery(query);
        const relevantDocs = await getRelevantDocuments(queryVector);
        const context = relevantDocs.join("\n");
        const response = await generateResponse(context, query);
        
        return response;
    }
);

async function main() {
    let query = "What does the document talk about?";
    let response = await ragPipeline(query);

    console.log("Query", query);
    console.log("Response", response);

    // Set relevant metadata on the session level
    tracer.setMetadata({
        "experiment-id": 1234
    });

    // Simulate getting user feedback
    let userRating = 4;
    tracer.setFeedback({
        "rating": userRating,
        "comment": "The response was accurate and helpful."
    })
}

// Wrap execution entry with `tracer.trace`
await tracer.trace(() => main())
