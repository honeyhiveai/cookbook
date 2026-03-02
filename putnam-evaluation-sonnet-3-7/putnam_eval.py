import os
import json
from openai import OpenAI
from honeyhive import evaluate, enrich_span, evaluator, trace
import honeyhive as hh
from honeyhive.models import components, operations

# ---------------------------------------------------------------------------
# SETUP API KEYS
# ---------------------------------------------------------------------------
# Replace with your actual Anthropic API key.
ANTHROPIC_API_KEY = 'your anthropic api key'
os.environ["ANTHROPIC_API_KEY"] = ANTHROPIC_API_KEY

# Initialize the Anthropic client using the provided API key.
from anthropic import Anthropic
anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)

# ---------------------------------------------------------------------------
# DEFINE THE RESPONSE GENERATION FUNCTION
# ---------------------------------------------------------------------------
@trace(
    config={
        "model": "claude-3-7-sonnet-20250219",  # Specify the Claude 3.7 Sonnet model
        "provider": "Anthropic",  # Indicate the provider
    }
)
def generate_response(question, id, category, ground_truth):
    """
    This function takes a question and associated metadata, sends the prompt
    to the Claude 3.7 Sonnet model with thinking enabled, and returns the generated response.
    """
    completion = anthropic_client.messages.create(
        model="claude-3-7-sonnet-20250219",
        max_tokens=20000,
        temperature=0.0,
        thinking={
            "type": "enabled",
            "budget_tokens": 26000  # Allocate a substantial thinking budget for complex math problems
        },
        messages=[
            {"role": "user", "content": question}  # Send the question as the user's message
        ]
    )
    
    # Extract the thinking content and final response
    thinking_content = ""
    final_response = ""
    
    for content_block in completion.content:
        if content_block.type == "thinking":
            thinking_content += content_block.thinking
        elif content_block.type == "text":
            final_response += content_block.text
    
    # Use HoneyHive to add metadata and ground truth feedback to this span
    enrich_span(
        metadata={
            "question_id": id, 
            "category": category,
            "thinking": thinking_content  # Include the thinking process in metadata
        },
        feedback={"ground_truth": ground_truth}
    )
    
    return final_response

# ---------------------------------------------------------------------------
# DEFINE THE MAIN QA FUNCTION
# ---------------------------------------------------------------------------
def putnam_qa(inputs, ground_truth):
    """
    This function acts as the entry point for evaluating a Putnam question.
    It extracts the necessary details from the inputs and ground truth,
    then calls the generate_response function.
    
    Parameters:
      - inputs: dict containing question details.
      - ground_truth: dict containing the correct solution.
    """
    return generate_response(
        question=inputs['question'],
        id=inputs['question_id'],
        category=inputs['question_category'],
        ground_truth=ground_truth['solution']
    )

# ---------------------------------------------------------------------------
# DEFINE THE RESPONSE QUALITY EVALUATOR
# ---------------------------------------------------------------------------
@evaluator
def response_quality_evaluator(outputs, inputs, ground_truths):
    """
    This evaluator function uses a grading prompt to assess the quality
    of the AI-generated response against the ground truth.
    
    It sends the prompt to the Claude 3.7 Sonnet model and extracts a rating between 0 and 10.
    """
    import re  # Regular expressions used for parsing the rating.

    # Construct the LLM evaluator prompt with detailed instructions and evaluation criteria.
    grading_prompt = f"""
[Instruction]
Please act as an impartial judge and evaluate the quality of the response provided by an AI assistant to the user question displayed below. Your evaluation should consider the mentioned criteria. Begin your evaluation by providing a short explanation on how the answer performs on the evaluation criteria. Be as objective as possible. After providing your explanation, you must rate the response on a scale of 0 to 10 by strictly following this format: "Rating: [[<number>]]".

[Criteria]
Each solution is worth 10 points. The grading should be strict and meticulous, reflecting the advanced level of the Putnam Competition:
- 10 points: A complete, rigorous, and elegant solution with no errors or omissions.
- 9 points: A correct and complete solution with minor presentation issues.
- 7-8 points: Essentially correct but with minor gaps.
- 5-6 points: Significant progress is made but with substantial gaps or errors.
- 3-4 points: Some relevant progress but major parts are missing or incorrect.
- 1-2 points: Only the beginnings of a solution are present.
- 0 points: No significant progress is made.

Question: {inputs}

[The Start of AI Proof]
{outputs}
[The End of AI Proof]

[The Start of Ground Truth Proof]
{ground_truths.get("solution", "N/A")}
[The End of Ground Truth Proof]

[Evaluation With Rating]
"""

    # Send the grading prompt to Claude 3.7 Sonnet for evaluation
    completion = anthropic_client.messages.create(
        model="claude-3-7-sonnet-20250219",
        max_tokens=4000,
        messages=[{"role": "user", "content": grading_prompt}]
    )
    
    # Retrieve the evaluation text from the model's response
    evaluation_text = ""
    for content_block in completion.content:
        if content_block.type == "text":
            evaluation_text += content_block.text

    # Use regex to extract the rating formatted as "Rating: [[<number>]]"
    match = re.search(r"Rating:\s*\[\[(\d+)\]\]", evaluation_text)
    if match:
        score = int(match.group(1))
        explanation = evaluation_text[:match.start()].strip()
    else:
        score = 0
        explanation = evaluation_text.strip()
    
    # Return the extracted score
    return score

# ---------------------------------------------------------------------------
# DEFINE THE THINKING PROCESS EVALUATOR
# ---------------------------------------------------------------------------
@evaluator
def thinking_process_evaluator(outputs, inputs, ground_truths, metadata):
    """
    This evaluator function assesses the quality of the thinking process
    used by the model to arrive at its solution.
    
    It evaluates how well the model breaks down the problem, identifies key concepts,
    and applies appropriate mathematical techniques.
    """
    import re  # Regular expressions used for parsing the rating.
    
    # Extract the thinking content from metadata
    thinking_content = metadata.get("thinking", "No thinking process recorded")
    
    # Construct the evaluator prompt for assessing the thinking process
    thinking_evaluation_prompt = f"""
[Instruction]
Please evaluate the quality of the AI assistant's thinking process as it worked through the mathematical problem below. Focus on how well the thinking process demonstrates:
1. Problem understanding and decomposition
2. Identification of relevant mathematical concepts and techniques
3. Logical progression of steps
4. Handling of edge cases and potential pitfalls
5. Clarity and organization of thought

After providing your explanation, rate the thinking process on a scale of 0 to 10 by strictly following this format: "Rating: [[<number>]]".

[Criteria]
- 10 points: Exceptional thinking process with perfect problem decomposition, optimal approach selection, and flawless reasoning.
- 8-9 points: Excellent thinking with clear understanding, appropriate techniques, and minor imperfections.
- 6-7 points: Good thinking with correct approach but some inefficiencies or unclear steps.
- 4-5 points: Adequate thinking that reaches partial solutions with some logical gaps.
- 2-3 points: Limited thinking with major conceptual misunderstandings or logical errors.
- 0-1 points: Poor thinking that fails to make meaningful progress toward a solution.

Question: {inputs}

[The Start of AI Thinking Process]
{thinking_content}
[The End of AI Thinking Process]

[The Start of Ground Truth Solution]
{ground_truths.get("solution", "N/A")}
[The End of Ground Truth Solution]

[Evaluation With Rating]
"""

    # Send the thinking evaluation prompt to Claude 3.7 Sonnet
    completion = anthropic_client.messages.create(
        model="claude-3-7-sonnet-20250219",
        max_tokens=4000,
        messages=[{"role": "user", "content": thinking_evaluation_prompt}]
    )
    
    # Retrieve the evaluation text from the model's response
    evaluation_text = ""
    for content_block in completion.content:
        if content_block.type == "text":
            evaluation_text += content_block.text

    # Use regex to extract the rating
    match = re.search(r"Rating:\s*\[\[(\d+)\]\]", evaluation_text)
    if match:
        score = int(match.group(1))
        explanation = evaluation_text[:match.start()].strip()
    else:
        score = 0
        explanation = evaluation_text.strip()
    
    # Return the extracted score
    return score

# ---------------------------------------------------------------------------
# DATASET CREATION AND LOADING
# ---------------------------------------------------------------------------
def create_dataset_if_not_exists(api_key, project_name, dataset_name):
    """
    Create a dataset if it doesn't already exist.
    Returns the dataset ID.
    """
    # Initialize HoneyHive client
    hhai = hh.HoneyHive(bearer_auth=api_key)
    
    # Try to find existing dataset
    try:
        datasets = hhai.datasets.get_datasets(project=project_name)
        for dataset in datasets.object:
            if dataset.name == dataset_name:
                print(f"Found existing dataset: {dataset_name} with ID: {dataset.id}")
                return dataset.id
    except Exception as e:
        print(f"Error checking existing datasets: {str(e)}")
    
    # Create new dataset
    try:
        print(f"Creating new dataset: {dataset_name}")
        eval_dataset = hhai.datasets.create_dataset(
            request=components.CreateDatasetRequest(
                project=project_name,
                name=dataset_name,
            )
        )
        dataset_id = eval_dataset.object.result.inserted_id
        print(f"Created dataset with ID: {dataset_id}")
        
        # Load Putnam problems
        with open('putnam_2023.jsonl', 'r') as f:
            problems = [json.loads(line) for line in f]
        
        # Add problems to dataset
        dataset_request = operations.AddDatapointsRequestBody(
            project=project_name,
            data=problems,
            mapping=operations.Mapping(
                inputs=['question', 'question_id', 'question_category'],
                ground_truth=['solution'],
                history=[]
            ),
        )
        
        datapoints = hhai.datasets.add_datapoints(
            dataset_id=dataset_id,
            request_body=dataset_request
        )
        
        print(f"Added {len(problems)} problems to dataset")
        return dataset_id
        
    except Exception as e:
        print(f"Error creating dataset: {str(e)}")
        raise

# ---------------------------------------------------------------------------
# RUN THE EVALUATION
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # HoneyHive credentials
    HH_API_KEY = 'your honeyhive api key'
    HH_PROJECT = 'your honeyhive project name'
    HH_DATASET_NAME = 'your dataset name'
    
    # Create or get dataset
    dataset_id = create_dataset_if_not_exists(HH_API_KEY, HH_PROJECT, HH_DATASET_NAME)
    
    # Run evaluation
    evaluate(
        function=putnam_qa,  # The main function that you're evaluating.
        hh_api_key=HH_API_KEY,  # HoneyHive API key
        hh_project=HH_PROJECT,  # HoneyHive project name
        name='your experiment name',  # Experiment name
        dataset_id=dataset_id,  # Dataset ID from creation step
        evaluators=[response_quality_evaluator, thinking_process_evaluator]  # List of evaluator functions
    )
    print("Putnam evaluation with Claude 3.7 Sonnet thinking completed and pushed to HoneyHive.") 