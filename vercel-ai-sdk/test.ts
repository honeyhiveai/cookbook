import "dotenv/config";
import { NodeSDK } from "@opentelemetry/sdk-node";
import { OTLPTraceExporter } from "@opentelemetry/exporter-trace-otlp-proto";
import { generateText, tool, stepCountIs } from "ai";
import { openai } from "@ai-sdk/openai";
import { z } from "zod";

const apiUrl = process.env.HH_API_URL || "https://api.honeyhive.ai";

const exporter = new OTLPTraceExporter({
  url: `${apiUrl}/opentelemetry/v1/traces`,
  headers: {
    "Authorization": `Bearer ${process.env.HH_API_KEY}`,
    "x-honeyhive": `project:${process.env.HH_PROJECT}`,
  },
});

const sdk = new NodeSDK({ traceExporter: exporter });
sdk.start();

console.log(`Exporting to: ${apiUrl}/opentelemetry/v1/traces (protobuf, OTel SDK v1)`);
console.log("Project:", process.env.HH_PROJECT);

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
  experimental_telemetry: {
    isEnabled: true,
    metadata: {
      sessionName: "vercel-ai-sdk-v1-test",
      source: "dev",
    },
  },
});

console.log("Result:", result.text);
console.log("Steps:", result.steps.length);

console.log("Flushing...");
await sdk.shutdown();
console.log("Done!");
