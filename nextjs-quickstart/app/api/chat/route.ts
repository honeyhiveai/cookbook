import { streamText } from 'ai';
import { createOpenRouter } from '@openrouter/ai-sdk-provider';

export async function POST(req: Request) {
  const { messages, sessionId } = await req.json();

  const openrouter = createOpenRouter({
    apiKey: process.env.OPENROUTER_API_KEY,
  });
  
  const result = streamText({
    model: openrouter('openai/gpt-4o-2024-11-20'),
    messages,
    experimental_telemetry: {
      isEnabled: true,
      metadata: {
        sessionId,
        sessionName: 'chat-session',
        project: 'my-honehyhive-project-name', // not needed if set in environment variable
        source: 'dev',
      },
    },
  });

  return result.toDataStreamResponse();
}