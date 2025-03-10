/**
 * transcriptsEval.js
 * 
 * This script demonstrates how to use HoneyHive's evaluation framework to
 * systematically evaluate the performance of an insurance call transcript
 * summarization system.
 * 
 * The script uses Azure OpenAI to generate summaries from call transcripts and
 * evaluates these summaries against a dataset stored in HoneyHive.
 */

import { evaluate } from "honeyhive";
import { AzureOpenAI } from "openai";

// Azure OpenAI configuration
// NOTE: These are placeholder values - replace with your actual credentials
const endpoint = "https://your-azure-openai-endpoint.openai.azure.com/";
const apiKey = "your-azure-openai-api-key";
const apiVersion = "2024-05-01-preview";
const deployment = "gpt-4o-mini";

/**
 * Function to summarize a transcript
 * 
 * This function takes input from the evaluation framework, generates a summary
 * using Azure OpenAI, and returns the summary along with metadata for analysis.
 * 
 * @param {Object} input - Object containing the transcript to summarize
 * @returns {Object} Object containing the summary and metadata
 */
export async function summarizeTranscript(input) {
  try {
    // Initialize Azure OpenAI client
    const client = new AzureOpenAI({ 
      endpoint, 
      apiKey,
      apiVersion,
      deployment 
    });

    // Prepare the prompt template
    const openaiFormatTemplate = [
      {
        "role": "system",
        "content": "You are an AI assistant that helps insurance agents summarize call transcripts."
      },
      {
        "role": "user",
        "content": `
You are an expert insurance claims analyst. Please summarize the following claims call transcript into key points:

1. Customer information
2. Claim details
3. Policy information
4. Next steps or actions

Transcript:
${input.transcript}

Please provide a concise summary with the most important information.`
      }
    ];

    // Define hyperparameters for the model
    const hyperparams = {
      temperature: 0.3,
      max_tokens: 500,
      top_p: 0.95,
      frequency_penalty: 0,
      presence_penalty: 0
    };

    // Generate the summary
    const result = await client.chat.completions.create({
      messages: openaiFormatTemplate,
      ...hyperparams,
      model: "", // Model is specified by the deployment ID in Azure
    });

    // Return the summary and metadata
    return {
      summary: result.choices[0].message.content,
      metadata: {
        tokenCount: {
          promptTokens: result.usage?.prompt_tokens || 0,
          completionTokens: result.usage?.completion_tokens || 0,
          totalTokens: result.usage?.total_tokens || 0
        },
        model: deployment
      }
    };
  } catch (error) {
    console.error("Error summarizing transcript:", error);
    throw error;
  }
}

/**
 * Main function to run the evaluation
 * 
 * This function sets up and executes the HoneyHive evaluation framework on
 * the transcript summarization function using a predefined dataset.
 */
async function main() {
  try {
    // Run the evaluation using HoneyHive's evaluate framework
    // NOTE: This is a placeholder API key - replace with your actual HoneyHive API key
    await evaluate({
      evaluationFunction: summarizeTranscript,
      hh_api_key: "your-honeyhive-api-key",
      hh_project: "your-honeyhive-project-name",
      name: "Claims Transcript Summary Eval",
      dataset_id: "your-dataset-id", // Replace with your actual dataset ID
      //server_url: "https://api.honeyhive.ai" //Optional, only required for self-hosted or dedicated-cloud deployments
    });
    
    console.log("Experiment completed successfully!");
  } catch (error) {
    console.error("Error running experiment:", error);
  }
}

// Execute the main function if this script is run directly
main();