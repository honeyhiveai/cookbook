import json
from datetime import datetime
import requests
from dotenv import load_dotenv
import os

hh_api_key = os.getenv('HH_API_KEY')
headers = {
  "Authorization": f"Bearer {hh_api_key}",
  "Content-Type": "application/json"
}

dataset_url = 'http://localhost:4785/datasets'
datapoint_url = 'http://localhost:4785/datapoints'

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

def get_datapoints_from_ids(project_id, datapoints_ids):
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

def export_dataset(dataset_name, project_id, size=None):
    print(f"Starting export of dataset: {dataset_name} for project ID: {project_id}")
    dataset = get_dataset_from_name(dataset_name, project_id)
    if dataset is None:
        print(f"Dataset {dataset_name} not found")
        return None
    else:
        print(f"Dataset {dataset_name} found successfully.")
    
    datapoints_ids = dataset['datapoints']
    print(f"Fetching datapoints for dataset: {dataset_name}")
    if size:
        datapoints_ids = datapoints_ids[:size]
    
    datapoints = get_datapoints_from_ids(project_id, datapoints_ids)
    if datapoints is None:
        print(f"Failed to fetch datapoints for dataset: {dataset_name}")
        return None
    else:
        print(f"Datapoints fetched successfully for dataset: {dataset_name}")

    dataset['datapoints'] = datapoints
    print(f"Export completed successfully for dataset: {dataset_name}")
    return dataset