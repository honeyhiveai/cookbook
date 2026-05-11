/**
 * transcriptsEval.js
 *
 * Evaluates the insurance call transcript summarization system using
 * HoneyHive's evaluation framework with Azure OpenAI.
 */

import { evaluate } from "honeyhive";
import { AzureOpenAI } from "openai";

// Azure OpenAI configuration from environment variables
const endpoint = process.env.AZURE_OPENAI_ENDPOINT || "https://your-azure-openai-endpoint.openai.azure.com/";
const apiKey = process.env.AZURE_OPENAI_API_KEY || "";
const apiVersion = "2024-10-21";
const deployment = process.env.AZURE_OPENAI_DEPLOYMENT || "gpt-4o-mini";

/**
 * Summarize a transcript for evaluation
 */
export async function summarizeTranscript(input) {
  const client = new AzureOpenAI({
    endpoint,
    apiKey,
    apiVersion,
    deployment,
  });

  const result = await client.chat.completions.create({
    messages: [
      {
        role: "system",
        content: "You are an AI assistant that helps insurance agents summarize call transcripts.",
      },
      {
        role: "user",
        content: `You are an expert insurance claims analyst. Please summarize the following claims call transcript into key points:

1. Customer information
2. Claim details
3. Policy information
4. Next steps or actions

Transcript:
${input.transcript}

Please provide a concise summary with the most important information.`,
      },
    ],
    temperature: 0.3,
    max_tokens: 500,
    model: "",
  });

  return {
    summary: result.choices[0].message.content,
  };
}

/**
 * Main function to run the evaluation
 */
async function main() {
  try {
    await evaluate({
      evaluationFunction: summarizeTranscript,
      hh_api_key: process.env.HH_API_KEY,
      hh_project: process.env.HH_PROJECT || "Claims Transcript Summary",
      name: "Claims Transcript Summary Eval",
      dataset_id: "your-dataset-id", // Replace with your actual HoneyHive dataset ID
    });

    console.log("Experiment completed successfully!");
  } catch (error) {
    console.error("Error running experiment:", error);
  }
}

main();
