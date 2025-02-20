import os
import asyncio
from openai import AsyncOpenAI, OpenAI
from honeyhive import evaluate, enrich_span, evaluator, atrace

# ---------------------------------------------------------------------------
# SETUP API KEYS
# ---------------------------------------------------------------------------
# Replace 'YOUR_OPENAI_API_KEY' with your actual OpenAI API key.
OPENAI_API_KEY = 'YOUR_OPENAI_API_KEY'
os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY

# DO NOT DO THIS
# Since we run evaluations concurrently, passing a global reference to the AsyncOpenAI client
# will result in all evaluations using the same client across threads and event loops.
# This will lead to asyncio related errors.
# openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# ---------------------------------------------------------------------------
# DEFINE THE RESPONSE GENERATION FUNCTION
# ---------------------------------------------------------------------------
@atrace(
    config={
        "model": "o3-mini",  # Optionally specify the model used for generating responses.
        "provider": "OpenAI",  # Optionally indicate the provider.
    }
)
async def generate_response(question, id, category, ground_truth):
    """
    This function takes a question and associated metadata, sends the prompt
    to the OpenAI model, and returns the generated response.
    """
    completion = await openai_client.chat.completions.create(
        model="o3-mini",
        messages=[
            {"role": "user", "content": question}  # Send the question as the user's message.
        ]
    )
    # Use HoneyHive to add metadata and ground truth feedback to this span.
    enrich_span(metadata={"question_id": id, "category": category},
                feedback={"ground_truth": ground_truth})
    return completion.choices[0].message.content

# ---------------------------------------------------------------------------
# DEFINE THE MAIN FUNCTION
# ---------------------------------------------------------------------------
def evaluation_task(inputs, ground_truth):
    """
    This function acts as the entry point for the evaluation.
    It extracts the necessary details from the inputs and ground truth,
    then calls the generate_response function using asyncio.run.

    This function will run concurrently for each datapoint in the dataset,
    have its own thread and isolated Python context, including its own asyncio event loop, 
    and will not interfere with other evaluations.

    This function may NOT be async and takes either 1 or 2 arguments.
    If it takes 1 argument, it is the input dictionary.
    If it takes 2 arguments, the first argument is the input dictionary
    and the second argument is the ground truth dictionary.
    
    Parameters:
      - inputs: dict containing question details.
      - ground_truth: dict containing the correct solution.
    """
    
    # Declare your globals inside the evaluation task function
    # This ensures that each evaluation task thread gets its own instance of the AsyncOpenAI client
    global openai_client
    openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

    return asyncio.run(generate_response(
        question=inputs['question'],
        id=inputs['question_id'],
        category=inputs['question_category'],
        ground_truth=ground_truth['solution']
    ))

# ---------------------------------------------------------------------------
# DEFINE THE RESPONSE QUALITY EVALUATOR
# ---------------------------------------------------------------------------
@evaluator
def response_quality_evaluator(outputs, inputs, ground_truths):
    """
    This evaluator function uses a grading prompt to assess the quality
    of the AI-generated response against the ground truth.
    
    It sends the prompt to the OpenAI model (configured with a different model)
    and extracts a rating between 0 and 10.
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

    # Send the grading prompt to another OpenAI model (here "o3-mini") for evaluation.
    client = OpenAI(api_key=OPENAI_API_KEY)
    completion = client.chat.completions.create(
        model="o3-mini",
        messages=[{"role": "user", "content": grading_prompt}]
    )
    # Retrieve the evaluation text from the model's response.
    evaluation_text = completion.choices[0].message.content

    # Use regex to extract the rating formatted as "Rating: [[<number>]]"
    match = re.search(r"Rating:\s*\[\[(\d+)\]\]", evaluation_text)
    if match:
        score = int(match.group(1))
        explanation = evaluation_text[:match.start()].strip()
    else:
        score = 0
        explanation = evaluation_text.strip()
    # Return the extracted score.
    return score

# ---------------------------------------------------------------------------
# RUN THE EVALUATION
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    evaluate(
        function=evaluation_task,  # The main function that you're evaluating.
        hh_api_key='YOUR_HONEYHIVE_API_KEY',  # Replace with your HoneyHive API key.
        hh_project='YOUR_HONEYHIVE_PROJECT_NAME',  # Replace with your HoneyHive project name.
        name='Putnam Q&A Eval', # Optionally replace the experiment name
        dataset_id='YOUR_HONEYHIVE_DATASET_ID',  # Replace with your dataset ID.
        evaluators=[response_quality_evaluator],  # List of evaluator functions defined in your code.
    )
    print("Putnam evaluation completed and pushed to HoneyHive.")
