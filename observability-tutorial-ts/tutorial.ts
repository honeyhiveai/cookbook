import * as dotenv from 'dotenv';
import { OpenAI } from 'openai';
import { Pinecone } from '@pinecone-database/pinecone';
import { HoneyHiveTracer } from "honeyhive";

dotenv.config();


const tracer: HoneyHiveTracer = await HoneyHiveTracer.init({
    apiKey: process.env.HH_API_KEY || '',
    project: process.env.HH_PROJECT || '',
    source: "dev", // e.g. "prod", "dev", etc.
    sessionName: "RAG Session",
});

const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY ||  '' });
const pc = new Pinecone({ apiKey: process.env.PINECONE_API_KEY || '' });
const index = pc.index("your-index-name");

const embedQuery = async (query: string) => {
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

const getRelevantDocuments = tracer.traceFunction({
    metadata: getRelevantDocumentsConfig
})(
    async function getRelevantDocuments(queryVector: number[]): Promise<string[]> {
        const queryResult = await index.query({
            vector: queryVector,
            topK: 3,
            includeMetadata: true
        });
        
        return queryResult.matches.map(item => item.metadata!._node_content as string);
    }
);

interface GenerateResponseConfig {
    model: string;
    prompt: string;
}

interface GenerateResponseMetadata {
    version: number;
}

const generateResponseConfig: GenerateResponseConfig = {
    "model": "gpt-4o",
    "prompt": "You are a helpful assistant" 
};

const generateResponseMetadata: GenerateResponseMetadata = {
    "version": 1
};

const generateResponse = tracer.traceFunction({
    metadata: {
        ...generateResponseConfig,
        ...generateResponseMetadata
    }
})(
    async function generateResponse(context: string, query: string): Promise<string> {
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

const ragPipeline = tracer.traceFunction()(
    async function ragPipeline(query: string): Promise<string> {
        const queryVector = await embedQuery(query);
        const relevantDocs = await getRelevantDocuments(queryVector);
        const context = relevantDocs.join("\n");
        const response = await generateResponse(context, query);
        
        return response;
    }
);

async function main(): Promise<void> {
    let query = "What does the document talk about?";
    let response = await ragPipeline(query);

    console.log("Query", query);
    console.log("Response", response);

    await tracer.enrichSession({metadata: {
        "experiment-id": 1234
    }});

    let userRating = 4;

    await tracer.enrichSession({feedback: {
        "rating": userRating,
        "comment": "The response was accurate and helpful."
    }});
}

await tracer.trace(() => main())
