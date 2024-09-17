import * as dotenv from 'dotenv';
import { OpenAI } from 'openai';
import { Pinecone } from '@pinecone-database/pinecone';
import { HoneyHiveTracer } from 'honeyhive';

dotenv.config();

// Initialize clients
const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
const pc = new Pinecone();
const index = pc.index("chunk-size-512");

async function embedQuery(query: string): Promise<number[]> {
    const res = await openai.embeddings.create({
        model: "text-embedding-ada-002",
        input: query
    });
    return res.data[0].embedding;
}

async function getRelevantDocuments(query: string): Promise<string[]> {
    const queryVector = await embedQuery(query);
    const res = await index.query({
        vector: queryVector,
        topK: 3,
        includeMetadata: true
    });
    return res.matches.map(item => item.metadata!._node_content as string);
}

async function generateResponse(context: string, query: string): Promise<string> {
    const prompt = `Context: ${context}\n\nQuestion: ${query}\n\nAnswer:`;
    const response = await openai.chat.completions.create({
        model: "gpt-4",
        messages: [
            { role: "system", content: "You are a helpful assistant." },
            { role: "user", content: prompt }
        ]
    });
    return response.choices[0].message.content || "";
}

async function ragPipeline(query: string): Promise<string> {
    const docs = await getRelevantDocuments(query);
    const response = await generateResponse(docs.join("\n"), query);
    return response;
}

async function main() {
    // Initialize HoneyHive Tracer
    const tracer = await HoneyHiveTracer.init({
        apiKey: process.env.HH_API_KEY!,
        project: process.env.HH_PROJECT!,
        source: "dev",
        sessionName: "TS RAG Session"
    });

    await tracer.trace(async () => {
        const query = "What does the document talk about?";
        const response = await ragPipeline(query);
        console.log(`Query: ${query}`);
        console.log(`Response: ${response}`);
    });

    tracer.setMetadata({
        "experiment-id": 123
    });

    // Simulate getting user feedback
    const userRating = 4;
    tracer.setFeedback({
        rating: userRating,
        comment: "The response was accurate and helpful."
    });
}

main().catch(console.error);