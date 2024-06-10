from dotenv import load_dotenv
import os
load_dotenv()

import requests
import re
from datetime import datetime
from openai import OpenAI
client = OpenAI(api_key="OPENAI_API_KEY")
openrouter_client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key="OPENROUTER_API_KEY")

import tiktoken
encoding = tiktoken.get_encoding("cl100k_base")
encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")

from metrics.model_metrics import ground_truth_match

import ollama

event_url = 'http://localhost:4785/events'

hh_api_key = os.getenv('HH_API_KEY')
headers = {
    "Authorization": f"Bearer {hh_api_key}",
    "Content-Type": "application/json"
}

def replace_variables(messages, input_dict):
    for key, value in input_dict.items():
        if not isinstance(value, str):
            value = str(value)
        # print(f"Running model with input: {key}={value}")
        pattern = r"\{\{" + re.escape(key) + r"\}\}"
        for message in messages:
            try:
                if re.search(pattern, message["content"]):
                    # print(f"Regex found for value {value} in message")
                    message["content"] = re.sub(pattern, value, message["content"])
            except re.error as regex_err:
                print(f"Regex error occurred: {regex_err}")
    return messages

def model_completion(project_id, session_id, messages, provider, model, inputs, ground_truth=None, SYSTEM_PROMPT=None, USER_PROMPT=None, evaluation_id=None):
    start = datetime.now()
    completion = None
    completion_final = None
    if provider == "openai":
        completion = client.chat.completions.create(model=model, messages=messages)
        completion_final = completion.choices[0].message.content
    elif provider == "openrouter":
        completion = openrouter_client.chat.completions.create(model=model, messages=messages)
        completion_final = completion.choices[0].message.content
    elif provider == "ollama":
        completion =  ollama.chat(model=model, messages=messages)
        completion_final =  completion['message']['content']
    completion_encoding = encoding.encode(completion_final)
    completion_length = len(completion_encoding)
    end = datetime.now()
    duration_seconds = (end - start).total_seconds()
    duration_milliseconds = duration_seconds * 1000
    tps = completion_length / duration_seconds

    # Ground truth match
    if ground_truth:
        gt_rating, gt_rating_exp = ground_truth_match(completion_final, ground_truth)

    event_name = "Model Summary"
    event_type = "model"
    parent_id = session_id
    data = {
        "event": {
            "project": project_id,
            "event_name": event_name,
            "event_type": event_type,
            "parent_id": parent_id,
            "inputs": {**inputs, "chat_history": messages},
            "outputs": {"output": completion_final},
            "source": "evaluation",
            "duration": duration_milliseconds,
            "user_properties": {},
            "metadata": {
                "completion_length": completion_length,
                "run_id": evaluation_id
            },
            "start_time": str(start),
            "end_time": str(end),
            "children_ids": [],
            "config": {
                "model": model,
                "provider": provider,
                "template": [{
                    "role": "system",
                    "content": SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": USER_PROMPT
                }
                ]
            },
            "metrics": {
                "tokens_per_second": tps,
                "completion_length": completion_length,
                "ground_truth_match": gt_rating,
                "ground_truth_match_exp": gt_rating_exp
            },
            "feedback": {
                "ground_truth": ground_truth
            },
            "session_id": session_id
        }
    }

    try:
        response = requests.request("POST", event_url, json=data, headers=headers)
        response.raise_for_status()  # This will raise an HTTPError if the response was unsuccessful
        event_id = response.json()["event_id"]
        print(f"Request successful! Event ID: {event_id}")
        return event_id
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")  # Python 3.6
        return None
    except requests.exceptions.RequestException as req_err:
        print(f"Error occurred: {req_err}")  # Python 3.6
        return None

def run_pipeline(project_id, datapoint, SYSTEM_PROMPT, USER_PROMPT, provider, model, evaluation_id):
   # we need to start the session and get the session_id
    error = None
    question = datapoint['inputs']['inputs']
    gt_array = datapoint['metadata']['multiple_choice_scores']
    ground_truth = None
    if gt_array and len(gt_array) > 0:
        if gt_array[0] == 1:
            ground_truth = "Yes"
        elif gt_array[1] == 1:
            ground_truth = "No"
        else:
            ground_truth = "N/A"

    datapoint_id = datapoint['_id']

    session_id = ""
    session_url = 'http://localhost:4785/session/start'
    session = {
        "session": {
            "project": project_id,
            "source": "evaluation",
            "event_name": "Session",
            "inputs": {
                "question": question
            },
            "metadata": {
                "datapoint_id": datapoint_id,
                "ground_truth": ground_truth,
                "run_id": evaluation_id
            },
            "user_properties": {
                "ground_truth": ground_truth,
                "full_answer": datapoint['ground_truth']['targets'][0] if 'ground_truth' in datapoint and 'targets' in datapoint['ground_truth'] and len(datapoint['ground_truth']['targets']) > 0 else ""
            },
        }
    }

    try:
        response = requests.request("POST", session_url, json=session, headers=headers)
        response.raise_for_status()  # Ensure we raise an exception for bad responses
        session_id = response.json()['session_id']
        print(response.json())
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
        error = http_err
    except Exception as e:
        print(f"Error creating session in /session/start: {e}")
        error = e
    
    if (error):
        # here we should log the event with the /events POST endpoint
        return None

    input_dict = {
        "question": question
    }

    chat_history = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": USER_PROMPT},
    ]

    messages = replace_variables(chat_history, input_dict)
    # LLM
    event_id = model_completion(project_id, session_id, messages, provider, model, input_dict, ground_truth, SYSTEM_PROMPT, USER_PROMPT, evaluation_id)

    return_dict = {
        "event_ids": [event_id],
        "session_id": session_id
    }
    
    return return_dict