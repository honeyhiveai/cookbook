from dotenv import load_dotenv
import os
load_dotenv()
import json
import requests

hh_api_key = os.getenv('HH_API_KEY')
headers = {
    "Authorization": f"Bearer {hh_api_key}",
    "Content-Type": "application/json"
}

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

def get_events_from_event_ids(event_ids):
    url = "http://localhost:4785/evals/events"
    reqBody = {
        "projectId": "648f6f2cd97aa222cef53da9",
        "eventList": json.dumps(event_ids)
    }

    try:
        response = requests.get(url, params=reqBody, headers=headers)
        response.raise_for_status()
        events = response.json()
        return events
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred while fetching events: {http_err}")
    except Exception as err:
        print(f"An unexpected error occurred while fetching events: {err}")
        return None

if __name__ == '__main__':
    run_id = "ec76a8f3-cad3-48fe-a88f-f229f131be90"
    evaluation = get_evaluation_from_run_id(run_id)
    event_ids = evaluation['event_ids']
    print(f"Event IDs: {event_ids}")
    events = []
    if event_ids is not None and isinstance(event_ids, list):
        for i in range(0, len(event_ids), 100):
            batch_event_ids = event_ids[i:i+100]
            print(f"Fetching batch {i//100+1}/{(len(event_ids)-1)//100+1}")
            batch_events = get_events_from_event_ids(batch_event_ids)
            print('Batch events:', batch_events)
            if batch_events is not None:
                print(f"Fetched {len(batch_events)} events.")
                events.extend(batch_events)
    with open('events.json', 'w') as file:
        json.dump(events, file)
    print(f"Events fetched successfully.")
