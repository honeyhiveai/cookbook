# Evaluating Advanced Mathematical Reasoning with Claude 3.7 Sonnet and Extended Thinking

This tutorial demonstrates how to evaluate Claude 3.7 Sonnet's mathematical reasoning capabilities on the challenging Putnam 2023 competition problems using Anthropic's extended thinking feature and HoneyHive for evaluation tracking.

## Overview

The William Lowell Putnam Mathematical Competition is the preeminent mathematics competition for undergraduate college students in North America, known for its exceptionally challenging problems that test deep mathematical thinking and rigorous proof writing abilities.

This evaluation leverages Claude 3.7 Sonnet's extended thinking capabilities, which allow the model to show its step-by-step reasoning process before delivering a final answer. This is particularly valuable for complex mathematical problems where the reasoning path is as important as the final solution.

## Key Features

- **Extended Thinking**: Uses Claude 3.7 Sonnet's thinking tokens to capture the model's internal reasoning process
- **Dual Evaluation**: Assesses both the final solution quality and the thinking process quality
- **Comprehensive Metrics**: Tracks performance across different types of mathematical problems
- **HoneyHive Integration**: Stores and visualizes evaluation results for analysis

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Setup](#setup)
3. [Configuration](#configuration)
4. [Running the Evaluation](#running-the-evaluation)
5. [Understanding the Results](#understanding-the-results)
6. [Advanced Usage](#advanced-usage)
7. [Troubleshooting](#troubleshooting)

## Prerequisites

Before you begin, make sure you have:

- **Python 3.10+** installed
- An **Anthropic API key** with access to Claude 3.7 Sonnet
- A **HoneyHive API key**, along with your **HoneyHive project name** and **dataset ID**
- The Putnam 2023 questions and solutions in the provided JSONL file

## Setup

1. **Clone the repository** (if you haven't already):
   ```bash
   git clone https://github.com/honeyhiveai/cookbook
   cd putnam-evaluation-sonnet-3-7
   ```

2. **Create and activate a virtual environment**:
   ```bash
   # Create a virtual environment
   python -m venv putnam_eval_env

   # On macOS/Linux:
   source putnam_eval_env/bin/activate

   # On Windows:
   putnam_eval_env\Scripts\activate
   ```

3. **Install required packages**:
   ```bash
   pip install -r requirements.txt
   ```

## Configuration

Open the `putnam_eval.py` script and update the following:

### Update API Keys

Replace the placeholder API keys with your actual keys:

```python
# Replace with your actual Anthropic API key
ANTHROPIC_API_KEY = 'YOUR_ANTHROPIC_API_KEY'
os.environ["ANTHROPIC_API_KEY"] = ANTHROPIC_API_KEY

# In the main execution block, update HoneyHive credentials
evaluate(
    function=putnam_qa,
    hh_api_key='YOUR_HONEYHIVE_API_KEY',
    hh_project='YOUR_HONEYHIVE_PROJECT_NAME',
    name='Putnam Q&A Eval with Claude 3.7 Sonnet Thinking',
    dataset_id='YOUR_HONEYHIVE_DATASET_ID',
    evaluators=[response_quality_evaluator, thinking_process_evaluator]
)
```

### Adjust Thinking Budget (Optional)

You can modify the thinking token budget based on your needs:

```python
completion = anthropic_client.messages.create(
    model="claude-3-7-sonnet-20250219",
    max_tokens=20000,
    thinking={
        "type": "enabled",
        "budget_tokens": 16000  # Adjust this value as needed
    },
    messages=[
        {"role": "user", "content": question}
    ]
)
```

## Running the Evaluation

1. **Prepare your dataset**:
   - The included `putnam_2023.jsonl` file contains the Putnam 2023 competition problems
   - Upload this dataset to HoneyHive following their [dataset import guide](https://docs.honeyhive.ai/datasets/import)

2. **Execute the evaluation script**:
   ```bash
   python putnam_eval.py
   ```

3. **Monitor progress**:
   - The script will process each problem in the dataset
   - Progress will be displayed in the terminal
   - Results will be pushed to HoneyHive for visualization

## Understanding the Results

The evaluation produces two key metrics for each problem:

1. **Solution Quality Score (0-10)**:
   - Assesses the correctness, completeness, and elegance of the final solution
   - Based on the strict grading criteria of the Putnam Competition

2. **Thinking Process Score (0-10)**:
   - Evaluates the quality of the model's reasoning approach
   - Considers problem decomposition, technique selection, and logical progression

In HoneyHive, you can:
- Compare performance across different problem types
- Analyze where the model excels or struggles
- Identify patterns in reasoning approaches

## Advanced Usage

### Adjusting Evaluation Criteria

You can modify the evaluation prompts in both evaluator functions to focus on specific aspects of mathematical reasoning:

```python
# In response_quality_evaluator
grading_prompt = f"""
[Instruction]
Please act as an impartial judge and evaluate...
"""

# In thinking_process_evaluator
thinking_evaluation_prompt = f"""
[Instruction]
Please evaluate the quality of the AI assistant's thinking process...
"""
```

### Streaming Responses

For real-time monitoring of the model's thinking process, you can implement streaming:

```python
with anthropic_client.messages.stream(
    model="claude-3-7-sonnet-20250219",
    max_tokens=20000,
    thinking={
        "type": "enabled",
        "budget_tokens": 16000
    },
    messages=[{"role": "user", "content": question}]
) as stream:
    for event in stream:
        # Process streaming events
        pass
```

## Troubleshooting

### Common Issues

1. **API Key Errors**:
   - Ensure your Anthropic API key is valid and has access to Claude 3.7 Sonnet
   - Check that environment variables are properly set

2. **Timeout Errors**:
   - Complex problems may require longer processing time
   - Consider implementing retry logic for long-running requests

3. **Memory Issues**:
   - Processing thinking content for all problems may require significant memory
   - Consider batching evaluations for large datasets

### Getting Help

If you encounter issues:
- Check the [Anthropic API documentation](https://docs.anthropic.com/claude/reference/getting-started-with-the-api)
- Visit the [HoneyHive documentation](https://docs.honeyhive.ai/)