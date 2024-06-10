import requests
from dotenv import load_dotenv
import os
load_dotenv()
from datetime import datetime

import tiktoken
encoding = tiktoken.get_encoding("cl100k_base")
encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")

hh_api_key = os.getenv('HH_API_KEY')
headers = {
    "Authorization": f"Bearer {hh_api_key}",
    "Content-Type": "application/json"
}

def start_evaluation(project_id, configuration, evaluation_name, dataset_name):
    runs_url = 'http://localhost:4785/runs'
    data = {
        "project": project_id,
        "name": evaluation_name,
        "event_ids": [],
        "datapoint_ids": [],
        "evaluators": [], # might have to change
        "configuration": configuration,
        "metadata": {},
        "passing_ranges": {}, # need to set up
        "dataset_id": f"{dataset_name}",
        "status": "pending",
    }

    try:
        response = requests.post(runs_url, headers=headers, json=data)
        response.raise_for_status()
        print('Evaluation started successfully with run_id: ', response.json()['run_id'])
        evaluation_id = response.json()['run_id']
        return evaluation_id
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred while starting evaluation: {http_err}")
    except Exception as err:
        print(f"An unexpected error occurred while starting evaluation: {err}")
        return None
    
def finish_evaluation(evaluation_id):
    url = f'http://localhost:4785/runs/{evaluation_id}'
    data = {"status": "completed"}

    try:
        response = requests.put(url, json=data, headers=headers)
        print(f"Status updated: {response.json()}")
    except Exception as e:
        print(f"Error updating status: {e}")

def post_event_to_evaluation(evaluation_id, event_ids, session_ids):
    url = f'http://localhost:4785/runs/{evaluation_id}'

    data = {
        "run_id": evaluation_id,
        "event_ids": event_ids,
        "session_ids": session_ids,
    }

    try:
        response = requests.request("PUT", url, json=data, headers=headers)
        response.raise_for_status()
        print('Events posted to evaluation successfully.')
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred while posting events to evaluation: {http_err}")
    except Exception as err:
        print(f"An unexpected error occurred while posting events to evaluation: {err}")

def get_evaluation_from_run_id(run_id):
    url = f'http://localhost:4785/runs/{run_id}'

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        evaluation = response.json()
        return evaluation['evaluation']
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred while fetching evaluation: {http_err}")
    except Exception as err:
        print(f"An unexpected error occurred while fetching evaluation: {err}")
        return None