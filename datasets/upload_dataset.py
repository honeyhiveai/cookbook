import json
from datetime import datetime
import requests
import csv
from dotenv import load_dotenv
import os

hh_api_key = os.getenv('HH_API_KEY')
headers = {
  "Authorization": f"Bearer {hh_api_key}",
  "Content-Type": "application/json"
}
project_id = "HH_PROJECT_ID"

dataset_url = 'http://localhost:4785/datasets'
datapoint_url = 'http://localhost:4785/datapoints'

dataset_name = "" # Name of the dataset 
dataset_description = """
""" # Description of the dataset
dataset_type = "evaluation" # or fine-tuning

filepath = '' # Path to the file to upload
input_fields = [] # array of input features. e.g. ['question', 'context']
output_fields = [] # array of output features. e.g. ['answer']

def convert_file_to_JSON(filepath):
    try:
        with open(filepath, 'r') as file:
            content = file.read().strip()
            if not content:
                print(f"File is empty: {filepath}")
                return None

        if filepath.endswith('.json'):
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                print("Failed to decode as JSON, trying as JSONL...")
                data = try_jsonl(content)
        elif filepath.endswith('.jsonl'):
            data = try_jsonl(content)
        elif filepath.endswith('.csv'):
            data = []
            with open(filepath, newline='') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    data.append(row)
        else:
            print(f"Unsupported file type for {filepath}")
            return None
        return data
    except Exception as e:
        print(f"Error converting file to JSON: {e}")
        return None

def try_jsonl(content):
    try:
        data = []
        for line in content.splitlines():
            data.append(json.loads(line))
        return data
    except json.JSONDecodeError as e:
        print(f"Error reading JSONL content: {e}")
        return None
    
def create_empty_dataset(dataset_name, dataset_description, dataset_type, project_id):
    dataset_id = None
    
    now = datetime.now()
    current_date = now.strftime("%Y-%m-%d")

    data = {
        'project': project_id,
        'created_at': str(current_date),
        'updated_at': str(current_date),
        'name': dataset_name,
        'description': dataset_description,
        'type': dataset_type,
        'linked_evals': [],
        'saved': True,
        'pipeline_type': 'events',
        'metadata': []
    }

    print('dataset',  data)

    response = requests.request("POST", dataset_url, json=data, headers=headers)
    if response.status_code == 200:
        print("Success:", response.json())
        dataset_id = response.json()['result']['insertedId']
    else:
        print("An error occurred:", response.status_code)

    return dataset_id

def upload_datapoint(datapoint, datapoints_ids, input_fields, output_fields, dataset_id):
    now = datetime.now()
    current_date = now.strftime("%Y-%m-%d")
    inputs_json = {field: datapoint[field] for field in input_fields}  # create a json object from the input_fields array
    outputs_json = {field: datapoint[field] for field in output_fields}  # create a json object from the output_fields array
    new_dp = {
        "project": project_id,
        "created_at": current_date,
        "updated_at": current_date,
        "inputs": inputs_json,
        "history": [],
        "ground_truth": outputs_json,
        "linked_event": "N/A",
        'linked_evals': [],
        "linked_datasets": [dataset_id],
        "saved": True,
        "type": "evaluation",
        "metadata": {key: (value.isoformat() if isinstance(value, datetime) else value) for key, value in datapoint.items() if key not in input_fields + output_fields}
    }

    response = requests.request("POST", datapoint_url, json=new_dp, headers=headers)
    if response and response.status_code == 200:
        datapoint_id = response.json()['result']['insertedId']
        print('Datapoint created with ID:', datapoint_id)
        datapoints_ids.append(response.json()['result']['insertedId'])
        # Now let's add the datapoint to the dataset immediately after creation
        data = {
            'dataset_id': dataset_id,
            "datapoints": datapoints_ids,
        }
        update_response = requests.request("PUT", dataset_url, json=data, headers=headers)
        if update_response and update_response.status_code == 200:
            print("Datapoint successfully added to the dataset")
        else:
            print("An error occurred while adding the datapoint to the dataset:", update_response.status_code)
    else:
        print("An error occurred:", response.status_code)
        print("Error message:", response.content)

def upload_dataset_from_json(data, dataset_name, dataset_description, project_id, input_fields, output_fields):
    datapoints = []
    for datapoint in data:
        datapoints.append(datapoint)

    dataset_id = create_empty_dataset(dataset_name, dataset_description, dataset_type, project_id)
    if dataset_id is None:
        print("Error creating dataset")
        print("Exiting...")
        return
    
    datapoints_ids = []
    for index, datapoint in enumerate(datapoints):
        print('creating datapoint', index, '/', len(datapoints), str(datapoint)[:50])
        upload_datapoint(datapoint, datapoints_ids, input_fields, output_fields, dataset_id)

def upload_dataset_from_file(filepath, dataset_name, dataset_description, project_id, input_fields, output_fields):
    data = convert_file_to_JSON(filepath)
    if data is None:
        print("Error converting file to JSON")
        print("Exiting...")
        return
    
    upload_dataset_from_json(data, dataset_name, dataset_description, project_id, input_fields, output_fields)

if __name__ == "__main__":
    upload_dataset_from_file(filepath, dataset_name, dataset_description, project_id, input_fields, output_fields)