# Text2SQL Evaluation Framework

## Overview

This repository contains a framework for evaluating Large Language Models (LLMs) on their ability to generate SQL queries from natural language questions. The framework uses DuckDB to execute the generated queries against an NBA dataset and evaluates the performance of different LLM providers (OpenAI, Google Gemini, and Anthropic).

## Features

- Supports multiple LLM providers:
  - OpenAI (GPT-4o)
  - Google Gemini (gemini-2.0-flash)
  - Anthropic (Claude 3.7 Sonnet)
- Automatic SQL query generation from natural language
- Query execution and validation using DuckDB
- Comprehensive evaluation metrics:
  - Execution success (no errors)
  - Result generation
  - SQL validity assessment
- Integration with HoneyHive for evaluation tracking and analysis
- Robust error handling and logging

## Requirements

- Python 3.8+
- Required packages:
  - duckdb
  - pandas
  - datasets
  - litellm
  - honeyhive
  - logging
  - re

## Setup

1. Clone the repository
2. Install dependencies:
   ```
   pip install duckdb pandas datasets litellm honeyhive
   ```
3. Set up API keys as environment variables:
   ```python
   os.environ["OPENAI_API_KEY"] = "your-openai-api-key"
   os.environ["GEMINI_API_KEY"] = "your-gemini-api-key"
   os.environ["ANTHROPIC_API_KEY"] = "your-anthropic-api-key"
   ```

## Usage

### Individual Evaluations

Run the script directly to perform individual evaluations on a set of predefined questions:

```bash
python text2sql_eval.py
```

This will:
1. Load the NBA dataset
2. Process each question with all three LLM providers
3. Execute the generated SQL queries
4. Display the results and any errors

### Batch Evaluations with HoneyHive

The framework integrates with HoneyHive for comprehensive evaluation tracking:

```python
evaluate(
    function=text2sql_openai,  # or text2sql_gemini, text2sql_anthropic
    hh_api_key="your-honeyhive-api-key",
    hh_project="text2sql-evals",
    name="text2sql_evaluation_openai",
    dataset=dataset,
    evaluators=[
        no_error_evaluator,
        has_results_evaluator,
        is_valid_sql_evaluator
    ]
)
```

## Evaluation Metrics

The framework uses three primary evaluators:

1. **No Error Evaluator**: Checks if the SQL query executed without errors
2. **Has Results Evaluator**: Verifies if the query returned any results
3. **SQL Validity Evaluator**: Uses an LLM to assess if the generated SQL is valid

## Architecture

The system follows this workflow:

1. **Input Processing**: Accepts natural language questions
2. **Query Generation**: Converts questions to SQL using the specified LLM
3. **Query Cleaning**: Removes markdown formatting from generated SQL
4. **Query Execution**: Runs the SQL against the NBA dataset using DuckDB
5. **Result Processing**: Formats and returns the execution results
6. **Evaluation**: Assesses the performance using multiple metrics

## Customization

### Adding New Models

To add support for a new LLM provider:

1. Create a new query generation function following the pattern of existing functions
2. Create a corresponding text2sql function for the new provider
3. Add the new function to the evaluation pipeline

### Custom Datasets

The framework can be adapted to work with different datasets:

1. Load your custom dataset
2. Register it with DuckDB
3. Update the system prompt with the new schema information

## Troubleshooting

Common issues:

- **API Key Errors**: Ensure all required API keys are correctly set
- **SQL Execution Errors**: Check the logs for detailed error messages
- **Markdown Formatting Issues**: The clean_sql_query function removes common markdown artifacts