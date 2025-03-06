# Insurance Claims Summarizer with AWS Bedrock and HoneyHive

This tutorial guides you through setting up and running an automated insurance claims summarization system using AWS Bedrock LLMs and HoneyHive's observability platform. The system processes insurance claim log notes and generates concise, focused summaries highlighting the nature of the claim, current status, actions taken, and next steps required.

This project demonstrates how to leverage advanced language models for structured summarization while implementing proper monitoring, tracing, and evaluation through HoneyHive.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Clone the Repository](#clone-the-repository)
3. [Setup Python Environment](#setup-python-environment)
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

- **Python 3.8+** installed
- An **AWS account** with Bedrock access
- **AWS credentials** (access key ID and secret access key)
- A **HoneyHive account** with API key
- **Insurance claim log data** (sample provided in `log_notes.jsonl`)

---

## 2. Clone the Repository

Open your terminal (or command prompt) and run the following commands:

```bash
git clone https://github.com/honeyhiveai/cookbook
cd claims-summarizer-python
```

## 3. Setup Python Environment

Create and activate a virtual environment to keep your dependencies isolated:

```bash
# Create a virtual environment
python -m venv claims_env

# On macOS/Linux:
source claims_env/bin/activate

# On Windows:
claims_env\Scripts\activate
```

## 4. Install Required Packages

Install the necessary Python packages using the provided requirements.txt:

```bash
pip install -r requirements.txt
```

This will install:
- boto3 (AWS SDK)
- honeyhive

## 5. Configure API Keys and Project Settings

You'll need to configure both scripts with your API keys and project settings:

### AWS Credentials

Set up your AWS credentials as environment variables:

```bash
# On macOS/Linux
export AWS_ACCESS_KEY_ID="your_aws_access_key"
export AWS_SECRET_ACCESS_KEY="your_aws_secret_key"
export AWS_REGION="us-west-2"  # or your preferred region with Bedrock access

# On Windows
set AWS_ACCESS_KEY_ID=your_aws_access_key
set AWS_SECRET_ACCESS_KEY=your_aws_secret_key
set AWS_REGION=us-west-2
```

Alternatively, configure AWS credentials using the AWS CLI:

```bash
aws configure
```

### HoneyHive API Key

Set your HoneyHive API key as an environment variable:

```bash
# On macOS/Linux
export HONEYHIVE_API_KEY="your_honeyhive_api_key"

# On Windows
set HONEYHIVE_API_KEY=your_honeyhive_api_key
```

## 6. Understanding the Scripts

This repository contains two main Python scripts:

### log_notes_trace.py

This script demonstrates how to use the ClaimSummarizer class with HoneyHive tracing:

```python
# Key components of log_notes_trace.py
# -------------------------------------

# Initialize HoneyHive
init_honeyhive()  # Sets up the connection to HoneyHive

# ClaimSummarizer class - generates summaries using AWS Bedrock
# The @trace() decorator captures execution data for HoneyHive
class ClaimSummarizer:
    # ...
    @trace()
    def generate_summary(self, log_content, max_sentences=8):
        # Generate and track LLM summaries

# Main function that demonstrates summarization of a sample claim
def main():
    # Initialize the summarizer
    summarizer = ClaimSummarizer()
    
    # Generate summary and print the result
    summary = summarizer.generate_summary(sample_log, max_sentences=6)
```

### log_notes_eval.py

This script sets up a systematic evaluation of your claims summarization system:

```python
# Key components of log_notes_eval.py
# -----------------------------------

class ClaimSummarizer:
    # Similar to the trace.py version, but includes ground truth handling
    @trace()
    def generate_summary(self, log_content, max_sentences=8, ground_truth=None):
        # Generate summaries and include ground truth for evaluation
        
# Function to be used with HoneyHive's evaluate framework
def summarize_claim(inputs, ground_truths=None):
    # Processes inputs from the HoneyHive dataset
    
# Main function to run the evaluation
def main():
    # Run the HoneyHive evaluation
    evaluate(
        function=summarize_claim,
        hh_api_key=os.environ.get("HONEYHIVE_API_KEY"),
        hh_project="Insurance Claims Summarization",
        name="Claims Summarizer Evaluation",
        dataset_id="your_dataset_id_here",  # Replace with actual dataset ID
        evaluators=[...]
    )
```

## 7. Prepare the Dataset

The repository includes a sample dataset file `log_notes.jsonl` containing insurance claim log entries. You'll need to:

1. Upload this dataset to HoneyHive:
   - Log in to your HoneyHive account
   - Go to the "Datasets" section
   - Click "Create Dataset" or "Import"
   - Upload the `log_notes.jsonl` file
   - Name your dataset (e.g., "Insurance Claim Logs")

2. Copy the Dataset ID:
   - After uploading, HoneyHive will provide a dataset ID
   - Copy this ID - you'll need it for the evaluation script

3. Update the `log_notes_eval.py` script:
   - Replace `your_dataset_id_here` with the actual dataset ID

## 8. Run Tracing Demo

To run the basic tracing demo:

```bash
python log_notes_trace.py
```

This script will:
- Initialize the HoneyHive tracer
- Process a sample insurance claim
- Generate a summary using AWS Bedrock
- Send trace data to HoneyHive
- Print the generated summary to the console

## 9. Run the Evaluation

Before running, make sure you've:
- Uploaded the dataset to HoneyHive
- Updated the dataset ID in the script
- Set your environment variables

Run the evaluation with:

```bash
python log_notes_eval.py
```

This script will:
- Process each claim log in your dataset
- Generate summaries using AWS Bedrock
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
- Check for any patterns in how the model handles different types of claims

## 11. Additional Notes

### Security Best Practices:
- **Never hardcode API keys** in your scripts
- Use environment variables or AWS IAM roles
- Keep your credentials secure and out of version control

### Model Customization:
- The scripts currently use Meta's Llama 3 70B model via AWS Bedrock
- You can modify the `model_id` parameter to try different models:
  ```python
  summarizer = ClaimSummarizer(model_id="anthropic.claude-3-sonnet-20240229-v1:0")
  ```

### Prompt Engineering:
- Examine the prompt templates to understand how they guide the model
- Adjust the prompt to focus on specific aspects of claims as needed

### Evaluation Strategies:
- Implement custom evaluators to assess specific criteria
- Consider aspects like accuracy, conciseness, and completeness
- Add human-in-the-loop feedback via the HoneyHive platform

By following these steps, you'll have a fully functional insurance claims summarization system with proper monitoring, tracing, and evaluation capabilities. The integration with HoneyHive provides valuable insights into model performance and helps identify opportunities for improvement.

Happy Summarizing!