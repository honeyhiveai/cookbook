import json
from datetime import datetime
import requests

hh_api_key = "HH_API_KEY"
headers = {
  "Authorization": f"Bearer {hh_api_key}",
  "Content-Type": "application/json"
}
project_id = "HH_PROJECT_ID"

dataset_url = 'https://api.honeyhive.ai/datasets'
datapoint_url = 'https://api.honeyhive.ai/datapoints'

dataset_name = "" # Name of the dataset to export

def get_dataset_from_name(dataset_name, project_id):
    data = {'project': project_id, 'type': 'evaluation'}
    
    try:
        response = requests.get(dataset_url, params=data, headers=headers)
        response.raise_for_status()  # Raises an HTTPError if the HTTP request returned an unsuccessful status code.
        datasets = response.json().get('testcases', [])  # Safely access 'datasets' key, defaulting to an empty list if not found.
        if not datasets:
            print('No datasets found.')
            return None
        print('Datasets fetched successfully.')
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred while fetching datasets: {http_err}")  # More specific error message
    except Exception as err:
        print(f"An unexpected error occurred while fetching datasets: {err}")  # General error message for any other exceptions
        return None

    for dataset in datasets:
        if dataset['name'] == dataset_name:
            return dataset

    return None

def get_datapoints_from_ids(datapoints_ids):
    batch_size=10
    datapoints = []

    for i in range(0, len(datapoints_ids), batch_size):
        batch_ids = datapoints_ids[i:i+batch_size]
        datapoint_param = {
            'project': project_id,
            'datapoint_ids': batch_ids,
        }
        try:
            response = requests.get(datapoint_url, params=datapoint_param, headers=headers)
            batch_datapoints = response.json()['datapoints']
            datapoints.extend(batch_datapoints)
            print(f"Batch {i//batch_size} fetched successfully")
        except Exception as e:
            print(f"Error fetching datapoints: {e}")
            return None

    return datapoints

def export_dataset(dataset_name, project_id):
    dataset = get_dataset_from_name(dataset_name, project_id)
    if dataset is None:
        print(f"Dataset {dataset_name} not found")
        return None
    
    datapoints_ids = dataset['datapoints']
    datapoints = get_datapoints_from_ids(datapoints_ids)

    dataset['datapoints'] = datapoints
    return dataset

if __name__ == '__main__':
    dataset = export_dataset(dataset_name, project_id)
    with open('results.txt', 'w') as file:
        file.write(str(dataset))
