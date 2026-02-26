import "dotenv/config";
import { NodeSDK } from "@opentelemetry/sdk-node";
import { OTLPTraceExporter } from "@opentelemetry/exporter-trace-otlp-http";
import { generateText, tool, streamText, stepCountIs } from "ai";
import { openai } from "@ai-sdk/openai";
import { z } from "zod";
import * as readline from "node:readline/promises";

// -------------------------------------------------------
// 1. Set up OpenTelemetry to send traces to HoneyHive
// -------------------------------------------------------
const exporter = new OTLPTraceExporter({
  url: `${process.env.HH_API_URL || "https://api.honeyhive.ai"}/opentelemetry/v1/traces`,
  headers: {
    "Authorization": `Bearer ${process.env.HH_API_KEY}`,
    "x-honeyhive": `project:${process.env.HH_PROJECT}`,
  },
});

const sdk = new NodeSDK({ traceExporter: exporter });
sdk.start();

// -------------------------------------------------------
// 2. Example: generateText with tools
// -------------------------------------------------------
async function singleTurn() {
  const result = await generateText({
    model: openai("gpt-4o-mini"),
    prompt: "What is the weather in San Francisco? Answer in celsius.",
    tools: {
      weather: tool({
        description: "Get the weather in a location (fahrenheit)",
        inputSchema: z.object({
          location: z.string().describe("The location to get the weather for"),
        }),
        execute: async ({ location }) => ({
          location,
          temperature: Math.round(Math.random() * (90 - 32) + 32),
        }),
      }),
    },
    stopWhen: stepCountIs(5),
    // --- HoneyHive: enable telemetry ---
    experimental_telemetry: {
      isEnabled: true,
      metadata: {
        sessionName: "vercel-ai-sdk-demo",
        source: "dev",
      },
    },
  });

  console.log("\n--- Single-turn result ---");
  console.log(result.text);
  console.log(`Steps: ${result.steps.length}`);
}

// -------------------------------------------------------
// 3. Example: streaming multi-turn chat
// -------------------------------------------------------
async function chatLoop() {
  const terminal = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
  });

  const messages: { role: "user" | "assistant"; content: string }[] = [];
  console.log('\n--- Chat mode (type "exit" to quit) ---\n');

  while (true) {
    const userInput = await terminal.question("You: ");
    if (userInput.toLowerCase() === "exit") break;

    messages.push({ role: "user", content: userInput });

    const result = streamText({
      model: openai("gpt-4o-mini"),
      messages,
      tools: {
        weather: tool({
          description: "Get the weather in a location (fahrenheit)",
          inputSchema: z.object({
            location: z
              .string()
              .describe("The location to get the weather for"),
          }),
          execute: async ({ location }) => ({
            location,
            temperature: Math.round(Math.random() * (90 - 32) + 32),
          }),
        }),
      },
      stopWhen: stepCountIs(5),
      // --- HoneyHive: enable telemetry ---
      experimental_telemetry: {
        isEnabled: true,
        metadata: {
          sessionName: "vercel-ai-sdk-demo",
          source: "dev",
        },
      },
    });

    let fullResponse = "";
    process.stdout.write("\nAssistant: ");
    for await (const delta of result.textStream) {
      fullResponse += delta;
      process.stdout.write(delta);
    }
    process.stdout.write("\n\n");

    messages.push({ role: "assistant", content: fullResponse });
  }

  terminal.close();
}

// -------------------------------------------------------
// Run
// -------------------------------------------------------
await singleTurn();
await chatLoop();

// Flush remaining spans before exit
await sdk.shutdown();
