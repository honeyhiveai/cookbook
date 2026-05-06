# Insurance Claims Transcript Summarizer (JavaScript)

This cookbook demonstrates an insurance call transcript summarization system using Azure OpenAI and HoneyHive for tracing and evaluation.

## Overview

- `transcriptsTrace.js` - Tracing demo: summarizes an example transcript with HoneyHive tracing
- `transcriptsEval.js` - Evaluation: runs batch evaluation against a HoneyHive dataset
- `transcripts.jsonl` - Sample call transcript data

## Setup

### Prerequisites

- Node.js 18+
- Azure OpenAI resource with a deployed model
- HoneyHive API key

### Installation

```bash
git clone https://github.com/honeyhiveai/cookbook.git
cd cookbook/claims-transcript-summarizer-js
npm install
```

### Configuration

Set environment variables:

```bash
export HH_API_KEY=your-honeyhive-api-key
export HH_PROJECT="Claims Transcript Summary"
export AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
export AZURE_OPENAI_API_KEY=your-azure-openai-key
export AZURE_OPENAI_DEPLOYMENT=gpt-4o-mini
```

## Usage

### Run Tracing Demo

```bash
node transcriptsTrace.js
```

The script initializes a HoneyHive tracer and uses `traceFunction` and `enrichSpan` to capture model invocations:

```javascript
import { HoneyHiveTracer } from "honeyhive";

const tracer = await HoneyHiveTracer.init({
  apiKey: process.env.HH_API_KEY,
  project: process.env.HH_PROJECT,
  sessionName: "Claims Transcript Summary",
});

const tracedFn = tracer.traceFunction({ eventType: "model" })(myFunction);
await tracer.trace(async () => {
  await tracedFn(input);
});
```

### Run Evaluation

1. Upload `transcripts.jsonl` to HoneyHive as a dataset
2. Copy the dataset ID and update it in `transcriptsEval.js`
3. Run:

```bash
node transcriptsEval.js
```

## References

- [HoneyHive Documentation](https://docs.honeyhive.ai/)
- [Azure OpenAI Documentation](https://learn.microsoft.com/en-us/azure/ai-services/openai/)
