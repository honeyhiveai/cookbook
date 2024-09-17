# Putnam 2023 AI Evaluation Tutorial (Python)

This directory contains a script for evaluating AI models on the Putnam 2023 Mathematical Competition questions using OpenAI's API and HoneyHive for observability.

## Prerequisites

- Python 3.10+
- OpenAI API key
- HoneyHive API key
- HoneyHive project and custom evaluator set up

## Setup

1. Clone this repository:
   ```
   git clone https://github.com/honeyhiveai/cookbook
   cd putnam-2023-ai-eval
   ```

2. Create a Python virtual environment:
   ```
   python -m venv putnam_eval_env
   source putnam_eval_env/bin/activate  # On Windows use `putnam_eval_env\Scripts\activate`
   ```

3. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

4. Update the API keys and project name in `putnam_eval_script.py`:
   - Replace `YOUR_HONEYHIVE_API_KEY` with your HoneyHive API key
   - Replace `YOUR_OPENAI_API_KEY` with your OpenAI API key
   - Replace `YOUR_HONEYHIVE_PROJECT_NAME` with your HoneyHive project name

5. Ensure you have the `putnam_2023.jsonl` file in the same directory as the script. This file should contain the Putnam 2023 questions and solutions.

6. Set up a custom LLM evaluator in HoneyHive:
   - Follow the instructions in the [HoneyHive documentation](https://docs.honeyhive.ai/evaluators/llm) to set up a custom LLM evaluator.
   - Configure the evaluator to trigger on the `process_question` event.
   - Use the following prompt template for the evaluator:

     ```
     [Instruction]
     Please act as an impartial judge and evaluate the quality of the response provided by an AI assistant to the user question displayed below. Your evaluation should consider the mentioned criteria. Begin your evaluation by providing a short explanation on how the answer performs on the evaluation criteria. Be as objective as possible. After providing your explanation, you must rate the response on a scale of 0 to 10 by strictly following this format: "[[rating]]", for example: "Rating: [[7]]".
     [Criteria]
     Each solution is worth 10 points. The grading should be strict and meticulous, reflecting the advanced level of the Putnam Competition:
     10 points: A complete, rigorous, and elegant solution with no errors or omissions. The proof is clear, concise, and demonstrates a deep understanding of the mathematical concepts involved.
     9 points: A correct and complete solution with minor presentation issues or slight inefficiencies. All key ideas are present and properly justified.
     7-8 points: A solution that is essentially correct but may have one or more minor gaps, imprecisions in reasoning, or areas where more elaboration is needed. The main approach is valid.
     5-6 points: A significant amount of progress is made, with the key ideas present, but there are more substantial gaps or errors in the reasoning. The solution is on the right track but incomplete.
     3-4 points: Some relevant progress is made, and some key insights are present, but major parts of the solution are missing or incorrect. The approach shows promise but falls short of a complete solution.
     1-2 points: The beginnings of a solution are present. There's evidence of understanding some aspects of the problem, but the majority of the necessary work is either missing or incorrect.
     0 points: No significant progress is made towards a solution, or the work presented is entirely off-track or irrelevant to the problem.
     Question: {{ inputs._params_.question }}
     [The Start of AI Proof]
     {{ outputs.result }}
     [The End of AI Proof]
     [The Start of Ground Truth Proof]
     {{ inputs._params_.ground_truth }}
     [The End of Ground Truth Proof]
     [Evaluation With Rating]
     ```

## Usage

Run the script:
```
python putnam_eval.py
```

## How It Works

This script evaluates AI models (specifically OpenAI's o1-preview) on the Putnam 2023 Mathematical Competition questions. It uses HoneyHive for observability and tracking. Here's a breakdown of what the script does:

1. Imports necessary libraries and sets up API keys
2. Creates a HoneyHive run for the evaluation
3. Loads the Putnam 2023 questions from a JSONL file
4. Defines functions to generate responses and process questions
5. Iterates through each question, sending it to the AI model and logging the results
6. Updates the HoneyHive run with the evaluation results

The script uses OpenAI's API to generate responses and HoneyHive's tracing functionality to log and analyze the results. This allows for detailed evaluation of the AI model's performance on complex mathematical problems.

The custom LLM evaluator set up in HoneyHive provides an impartial assessment of each AI-generated solution, grading it on a scale of 0 to 10 based on the Putnam Competition's rigorous standards.

## File Structure

- `putnam_eval.py`: The main Python script for running the evaluation
- `putnam_2023.jsonl`: JSONL file containing Putnam 2023 questions and solutions (not included in repo, must be provided)
- `README.md`: This file, containing instructions and explanations
- `requirements.txt`: File containing package requirements

## Notes

- Make sure to keep your API keys confidential and do not commit them to version control.
- The script is set up to use the "o1-preview" model from OpenAI. Adjust this if you want to evaluate different models.
- The evaluation results will be available in your HoneyHive project under the `Evaluations` tab.