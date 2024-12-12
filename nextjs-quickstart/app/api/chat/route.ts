import { openai } from '@ai-sdk/openai';
import { streamText } from 'ai';
import { HoneyHiveTracer } from "honeyhive";

async function initializeTracer(sessionName: string): Promise<HoneyHiveTracer> {
  const tracer = await HoneyHiveTracer.init({
      apiKey: process.env.HH_API_KEY!,
      project: process.env.HH_PROJECT!,
      sessionName: sessionName,
  });

  return tracer;
}

// Allow streaming responses up to 30 seconds
export const maxDuration = 30;

export async function POST(req: Request) {
  const { messages } = await req.json();

  const tracer = await initializeTracer('nextjs-ai-app');

  const result = streamText({
    model: openai('gpt-4o-mini'),
    messages,
    experimental_telemetry: {
      isEnabled: true,
      tracer: tracer.getTracer(),
    },
  });

  return result.toDataStreamResponse();
}