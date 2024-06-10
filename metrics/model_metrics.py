from dotenv import load_dotenv
import os
load_dotenv()

from openai import OpenAI
import requests
import re
from datetime import datetime
import json
client = OpenAI(api_key="OPENAI_API_KEY")


def ground_truth_match(response, ground_truth):
    print("Computing ground truth match...")
    # Use a model to grade the similarity between the response and the ground truth
    evaluator_model = "gpt-3.5-turbo-1106"
    evaluator_system_prompt = """
    You are provided with a response and a ground truth. 
    Rate the similarity between the response and the ground truth on a scale of 0 to 5. 0 means there are no similarity and 5 means they are very similar.
    """

    evaluator_user_prompt = f"""
    Response: {response}
    --------------------------------------------------
    Ground Truth: {ground_truth}
    """

    messages = [
        {"role": "system", "content": evaluator_system_prompt},
        {"role": "user", "content": evaluator_user_prompt},
    ]

    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_ground_truth_match",
                "description": "Rate the similarity between the response and the ground truth on a scale of 0 to 5. 0 means there are no similarity and 5 means they are very similar. Also, provide a brief explanation for your rating.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "rating": {
                            "type": "integer",
                            "description": "The similarity rating between the response and the ground truth on a scale of 0 to 5. 0 means there are no similarity and 5 means they are very similar.",
                        },
                        "explanation": {
                            "type": "string",
                            "description": "A brief explanation for your rating.",
                        },
                    },
                    "required": ["rating", "explanation"],
                },
            }
        }
    ]
    
    rating = 0
    explanation = "N/A"

    try:
        completion = client.chat.completions.create(model=evaluator_model, messages=messages, tools=tools, tool_choice={"type": "function", "function": {"name": "get_ground_truth_match"}})
    except Exception as e:
        print(f"Error occurred while running the evaluator model: {e}")
        explanation = f"Error occurred while running the evaluator model. Error: {e}"
        return rating, explanation
    
    try:
        arguments = json.loads(completion.choices[0].message.tool_calls[0].function.arguments)
    except json.JSONDecodeError:
        arguments = None
    
    if arguments is None:
        rating = 0
        explanation = "The model failed to provide a rating."
    elif "rating" in arguments and "explanation" in arguments:
        rating = arguments["rating"]
        explanation = arguments["explanation"]
    else:
        rating = 0
        explanation = "The model failed to provide a valid rating."
    # ChatCompletionMessage(content=None, role='assistant', function_call=None, tool_calls=[ChatCompletionMessageToolCall(id='call_z8ijGSoMLS7xcaU7MjLmpRL8', function=Function(arguments='{\n  "location": "Toronto, Canada",\n  "format": "celsius"\n}', name='get_current_weather'), type='function')])
    # now check that it's a number between 0 and 5
    if not isinstance(rating, int) or rating < 0 or rating > 5:
        rating = 0
        explanation = "The model failed to provide a valid rating."

    print(f"Ground truth match rating: {rating}")
    return rating, explanation