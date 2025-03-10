# Insurance Claims Transcript Summarizer with HoneyHive

This JavaScript cookbook demonstrates how to build an insurance claims call transcript summarization system using Azure OpenAI and HoneyHive for observability and evaluation. The system processes call transcripts, extracts key information, and generates concise summaries highlighting customer details, claim information, policy details, and next steps.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Clone the Repository](#clone-the-repository)
3. [Setup JavaScript Environment](#setup-javascript-environment)
4. [Install Required Packages](#install-required-packages)
5. [Configure API Keys and Project Settings](#configure-api-keys-and-project-settings)
6. [Understanding the Scripts](#understanding-the-scripts)
7. [Prepare the Dataset](#prepare-the-dataset)
8. [Run Tracing Demo](#run-tracing-demo)
9. [Run the Evaluation](#run-the-evaluation)
10. [Reviewing the Results](#reviewing-the-results)
11. [Additional Notes](#additional-notes)

---

## 1. Prerequisites

Before you begin, make sure you have:

- **Node.js** (v16.0 or higher) installed
- An **Azure OpenAI** account with API access
- A **HoneyHive account** with API key
- **Insurance call transcript dataset** (sample provided in `transcripts.jsonl`)

---

## 2. Clone the Repository

Open your terminal (or command prompt) and run the following commands:

```bash
git clone https://github.com/honeyhiveai/cookbook
cd claims-transcript-summarizer-js
```

## 3. Setup JavaScript Environment

This project uses ES modules. Make sure your package.json includes:

```json
{
  "type": "module"
}
```

## 4. Install Required Packages

Install the necessary JavaScript packages:

```bash
npm install honeyhive openai
```

## 5. Configure API Keys and Project Settings

You'll need to configure both scripts with your API keys and project settings:

### Azure OpenAI Credentials

Update the Azure OpenAI configuration in both scripts:

```javascript
// In both transcriptsTrace.js and transcriptsEval.js
const endpoint = "https://your-azure-openai-endpoint.openai.azure.com/";
const apiKey = "your-azure-openai-api-key";
const apiVersion = "2024-05-01-preview";
const deployment = "gpt-4o-mini";
```

### HoneyHive API Key

Update the HoneyHive configuration:

```javascript
// In transcriptsTrace.js
const tracer = await HoneyHiveTracer.init({
  apiKey: "your-honeyhive-api-key",
  project: "your-honeyhive-project-name",
  source: "dev",
  sessionName: "Claims Transcript Summary",
  //serverUrl: "https://api.honeyhive.ai" //Optional, only required for self-hosted or dedicated-cloud deployments
});

// In transcriptsEval.js
await evaluate({
  evaluationFunction: summarizeTranscript,
  hh_api_key: "your-honeyhive-api-key",
  hh_project: "your-honeyhive-project-name",
  name: "Claims Transcript Summary Eval",
  dataset_id: "your-dataset-id",
  //server_url: "https://api.honeyhive.ai" //Optional, only required for self-hosted or dedicated-cloud deployments
});
```

## 6. Understanding the Scripts

This repository contains two main JavaScript scripts:

### transcriptsTrace.js

This script demonstrates how to use the summarization function with HoneyHive tracing:

```javascript
// Key components of transcriptsTrace.js
// -----------------------------------

// Core summarization function
async function _summarizeTranscriptCore(transcript, enrichSpanCallback = null) {
  // Initialize Azure OpenAI client
  // Prepare prompt template
  // Generate summary using the LLM
  // Enrich tracing span with metadata if callback provided
}

// Simple function to summarize a single transcript
async function summarizeTranscript(transcript) {
  const result = await _summarizeTranscriptCore(transcript);
  return result.summary;
}

// Function to process multiple transcripts
async function processTranscripts(transcripts) {
  // Process each transcript and return array of results
}

// Main function that demonstrates HoneyHive tracing
async function main() {
  // Initialize HoneyHive tracer
  const tracer = await HoneyHiveTracer.init({ /* config */ });
  
  // Create traced version of summarize function
  const tracedSummarizeTranscript = tracer.traceFunction(/* ... */);
  
  // Execute traced function within a trace context
  await tracer.trace(async () => {
    const summary = await tracedSummarizeTranscript(exampleTranscript);
    console.log(summary);
  });
}
```

### transcriptsEval.js

This script sets up a systematic evaluation of your transcript summarization system:

```javascript
// Key components of transcriptsEval.js
// -----------------------------------

// Function to summarize a transcript for evaluation
export async function summarizeTranscript(input) {
  // Initialize Azure OpenAI client
  // Prepare prompt template
  // Generate summary using the LLM
  // Return summary and metadata for evaluation
}

// Main function to run the evaluation
async function main() {
  // Run the HoneyHive evaluation framework
  await evaluate({
    evaluationFunction: summarizeTranscript,
    hh_api_key: "your-honeyhive-api-key",
    hh_project: "Insurance Claims Summarization",
    name: "Claims Transcript Summarization Experiment",
    dataset_id: "your-dataset-id",
    server_url: "https://api.honeyhive.ai"
  });
}
```

## 7. Prepare the Dataset

The repository includes a sample dataset file `transcripts.jsonl` containing insurance call transcript entries. You'll need to:

1. Upload this dataset to HoneyHive:
   - Log in to your HoneyHive account
   - Go to the "Datasets" section
   - Click "Create Dataset" or "Import"
   - Upload the `transcripts.jsonl` file
   - Name your dataset (e.g., "Insurance Call Transcripts")

2. Copy the Dataset ID:
   - After uploading, HoneyHive will provide a dataset ID
   - Copy this ID - you'll need it for the evaluation script

3. Update the `transcriptsEval.js` script:
   - Replace `your-dataset-id` with the actual dataset ID

## 8. Run Tracing Demo

To run the basic tracing demo:

```bash
node transcriptsTrace.js
```

This script will:
- Initialize the HoneyHive tracer
- Process a sample insurance call transcript
- Generate a summary using Azure OpenAI
- Send trace data to HoneyHive
- Print the generated summary to the console

## 9. Run the Evaluation

Before running, make sure you've:
- Uploaded the dataset to HoneyHive
- Updated the dataset ID in the script
- Set your Azure OpenAI and HoneyHive credentials

Run the evaluation with:

```bash
node transcriptsEval.js
```

This script will:
- Process each call transcript in your dataset
- Generate summaries using Azure OpenAI
- Compare against ground truth when available
- Log all results to HoneyHive
- Execute any custom evaluators you've specified

## 10. Reviewing the Results

To review the evaluation results:

### View Traces in HoneyHive:
1. Log into your HoneyHive Dashboard
2. Navigate to your project
3. Check the "Traces" section to see detailed information about each model execution

### Review Evaluations:
1. Go to the "Experiments" tab in HoneyHive
2. Find your evaluation run
3. Explore metrics, summaries, and evaluation scores

### Analysis Features:
- Compare performance across different runs
- View metrics for summary quality
- Check for any patterns in how the model handles different types of calls

## 11. Additional Notes

### Security Best Practices:
- **Never hardcode API keys** in your scripts
- Use environment variables or secure configuration management
- Keep your credentials secure and out of version control

### Model Customization:
- The scripts currently use Azure OpenAI's GPT-4o-mini
- You can modify the `deployment` parameter to try different models
- Adjust hyperparameters like temperature and max_tokens for different styles of summaries

### Prompt Engineering:
- Examine the prompt templates to understand how they guide the model
- Adjust the prompt to focus on specific aspects of calls as needed
- Add examples to the prompt for better output consistency

### Evaluation Strategies:
- Implement custom evaluators to assess specific criteria
- Consider aspects like accuracy, conciseness, and completeness
- Add human-in-the-loop feedback via the HoneyHive platform

The dataset format for `transcripts.jsonl` should be:

```json
{
  "id": "CLM-24-66781G",
  "transcript": "CALL TRANSCRIPT - CLAIM #AC78394D\nDATE: 2024-02-15\n...",
  "ground_truth": "Customer: Michael Rodriguez\nPolicy: RAP-5683221\n..."
}
```

By following these steps, you'll have a fully functional insurance call transcript summarization system with proper monitoring, tracing, and evaluation capabilities. The integration with HoneyHive provides valuable insights into model performance and helps identify opportunities for improvement.