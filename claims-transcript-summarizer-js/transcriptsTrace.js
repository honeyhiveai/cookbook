/**
 * transcriptsTrace.js
 * 
 * This script demonstrates how to use HoneyHive's tracing capabilities to monitor 
 * and analyze the performance of an insurance claim call transcript summarization system.
 * 
 * The script uses Azure OpenAI to generate summaries from call transcripts and
 * traces the execution using HoneyHive for observability.
 */

import { AzureOpenAI } from "openai";
import { HoneyHiveTracer } from "honeyhive";

// Azure OpenAI configuration
// NOTE: These are placeholder values - replace with your actual credentials
const endpoint = "https://your-azure-openai-endpoint.openai.azure.com/";
const apiKey = "your-azure-openai-api-key";
const apiVersion = "2024-05-01-preview";
const deployment = "gpt-4o-mini";

// Example transcript for testing purposes
const exampleTranscript = `
CALL TRANSCRIPT - CLAIM #AC78394D
DATE: 2024-02-15
TIME: 10:32 AM EST
AGENT: Sarah Thompson
CUSTOMER: Michael Rodriguez

[Call begins]

AGENT: Thank you for calling Reliable Insurance Claims Department. This is Sarah speaking. How may I help you today?

CUSTOMER: Hi Sarah. My name is Michael Rodriguez. I had a car accident yesterday and need to file a claim.

AGENT: I'm sorry to hear about your accident, Mr. Rodriguez. I hope you're okay. I'll be happy to help you file a claim. May I have your policy number, please?

CUSTOMER: Yes, it's RAP-5683221.

AGENT: Thank you. I've pulled up your policy. Could you please verify your address and phone number?

CUSTOMER: Sure. It's 1425 Maple Avenue, Apartment 302, Springfield, IL, 62704. My phone number is 217-555-3892.

AGENT: Perfect, thank you. Now, could you please tell me about the accident? When and where did it occur?

CUSTOMER: It happened yesterday around 5:30 PM at the intersection of Oak Street and 5th Avenue. I was driving home from work, and someone ran a red light and hit the passenger side of my car.

AGENT: I'm sorry to hear that. Was anyone injured in the accident?

CUSTOMER: Thankfully, no. I was alone in the car, and the other driver seemed fine too. We both got out and exchanged information.

AGENT: That's good to hear. Did you contact the police?

CUSTOMER: Yes, they came and filed a report. The report number is SPD-2024-0214-1872.

AGENT: Excellent. Do you have the other driver's information?

CUSTOMER: Yes. His name is David Wilson. His insurance is with Capital Insurance, policy number CI-77239846. His phone number is 217-555-7734.

AGENT: Thank you for having all that information ready. What kind of damage did your vehicle sustain?

CUSTOMER: The passenger side door is badly dented, and the window is shattered. The front passenger tire also seems damaged, and the car pulls to the right when I drive it.

AGENT: I understand. Have you taken your vehicle to a repair shop yet?

CUSTOMER: Not yet. I wanted to file the claim first.

AGENT: That's fine. Your policy includes coverage for collision damages with a $500 deductible. It also provides for a rental car while your vehicle is being repaired.

CUSTOMER: That's great. How do I proceed with getting my car fixed?

AGENT: I recommend taking your vehicle to one of our approved repair shops. The closest one to your address would be Springfield Auto Body on Main Street. They can provide a detailed estimate of the damages.

CUSTOMER: OK, I'll do that. How soon can I get a rental car?

AGENT: Once you drop off your vehicle at the repair shop, you can pick up a rental from Enterprise Rent-A-Car next door. Just show them your claim number, which I'm generating right now.

CUSTOMER: Perfect. And how long will the whole process take?

AGENT: Based on the damages you've described, repairs typically take 5-7 business days, but the repair shop will give you a more accurate timeline after their assessment.

AGENT: Your claim number is CLM-24-78394D. I'll send all the details to your email, including next steps and contacts for the repair shop and rental company.

CUSTOMER: Great, thank you. My email is michael.rodriguez@email.com.

AGENT: I've got your email on file, and I'll send the information right away. Is there anything else I can help you with today?

CUSTOMER: No, that's all. Thank you for your help.

AGENT: You're welcome, Mr. Rodriguez. If you have any other questions, please don't hesitate to call us back or check the status of your claim on our website or mobile app. Have a good day.

CUSTOMER: You too. Goodbye.

[Call ends]
`;

/**
 * Core function to summarize transcripts using Azure OpenAI
 * 
 * @param {string} transcript - The call transcript to summarize
 * @param {Function} enrichSpanCallback - Optional callback to enrich the HoneyHive span with metadata
 * @returns {Object} An object containing the summary, configuration data, and metadata
 */
async function _summarizeTranscriptCore(transcript, enrichSpanCallback = null) {
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
{{transcript}}

Please provide a concise summary with the most important information.`
      }
    ];

    // Create a deep copy of the template and replace the placeholder with the actual transcript
    const filledMessages = JSON.parse(JSON.stringify(openaiFormatTemplate));
    filledMessages[1].content = filledMessages[1].content.replace("{{transcript}}", transcript);

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
      messages: filledMessages,
      ...hyperparams,
      model: "", // Model is specified by the deployment ID in Azure
    });

    // Prepare configuration data for tracing
    const configData = {
      model: deployment,
      template: openaiFormatTemplate,
      hyperparameters: hyperparams
    };
    
    // Prepare metadata for tracing
    const metadataData = {
      tokenCount: {
        promptTokens: result.usage?.prompt_tokens || 0,
        completionTokens: result.usage?.completion_tokens || 0,
        totalTokens: result.usage?.total_tokens || 0
      }
    };

    // Enrich the HoneyHive span with config and metadata if callback is provided
    if (enrichSpanCallback && typeof enrichSpanCallback === 'function') {
      enrichSpanCallback(configData, metadataData);
    }

    // Return the result
    return {
      summary: result.choices[0].message.content,
      configData,
      metadataData
    };
  } catch (error) {
    console.error("Error summarizing transcript:", error);
    throw error;
  }
}

/**
 * Function to summarize a single transcript
 * 
 * @param {string} transcript - The call transcript to summarize
 * @returns {string} The generated summary
 */
async function summarizeTranscript(transcript) {
  const result = await _summarizeTranscriptCore(transcript);
  return result.summary;
}

/**
 * Function to process multiple transcripts
 * 
 * @param {Array} transcripts - An array of transcript objects
 * @returns {Array} An array of objects containing transcript IDs and summaries
 */
async function processTranscripts(transcripts) {
  const results = [];
  
  for (const transcript of transcripts) {
    const result = await _summarizeTranscriptCore(transcript);
    results.push({
      transcript_id: transcript.id || 'unknown',
      summary: result.summary
    });
  }
  
  return results;
}

/**
 * Main function to demonstrate the use of HoneyHive tracing
 */
async function main() {
  try {
    // Initialize HoneyHive tracer
    // NOTE: This is a placeholder API key - replace with your actual HoneyHive API key
    const tracer = await HoneyHiveTracer.init({
      apiKey: "your-honeyhive-api-key",
      project: "your-honeyhive-project-name",
      source: "dev",
      sessionName: "Claims Transcript Summary",
      //serverUrl: "https://api.honeyhive.ai" //Optional, only required for self-hosted or dedicated-cloud deployments
    });

    // Create a traced version of the summarizeTranscript function
    const tracedSummarizeTranscript = tracer.traceFunction({eventType: "model"})(
      async function summarizeTranscript(transcript) {
        const result = await _summarizeTranscriptCore(transcript, (configData, metadataData) => {
          tracer.enrichSpan({
            config: configData,
            metadata: metadataData
          });
        });
        
        return result.summary;
      }
    );

    // Execute the traced function within a trace context
    await tracer.trace(async () => {
      console.log("Processing example transcript...");
      console.log("=================================");
      
      const summary = await tracedSummarizeTranscript(exampleTranscript);
      
      console.log("\n=== EXAMPLE TRANSCRIPT SUMMARY ===\n");
      console.log(summary);
      console.log("\n=================================\n");
    });
  } catch (error) {
    console.error("The sample encountered an error:", error);
  }
}

// Execute the main function if this script is run directly
main();

// Export functions for use in other modules
export { summarizeTranscript, processTranscripts, main };