import requests
from datasets.export_dataset import get_dataset_from_name, get_datapoints_from_ids
from datasets.edit_dataset import update_datapoints
from dotenv import load_dotenv
import os
load_dotenv()

dataset_name = os.getenv('DATASET_NAME')
project_id = os.getenv('HH_PROJECT_ID')

def validate_datapoint(datapoint):
    inputs = datapoint['inputs']
    outputs = datapoint['ground_truth']
    if len(inputs.keys()) == 1 and len(outputs.keys()) == 1:
        print(f"Valid datapoint: {str(datapoint)[:50]}")
        return True
    else:
        print(f"Invalid datapoint: {str(datapoint)[:50]}")
        return False

if __name__ == '__main__':
    dataset = get_dataset_from_name(dataset_name, project_id)
    final_datapoints = []
    if dataset:
        print(f"Dataset: {dataset_name} found.")
        datapoints = get_datapoints_from_ids(project_id, dataset['datapoints'])
        for datapoint in datapoints:
            if validate_datapoint(datapoint):
                final_datapoints.append(datapoint)

        response = update_datapoints(dataset_name, final_datapoints, dataset['_id'])
        if response:
            print(f"Datapoints updated successfully for dataset: {dataset_name}")
        else:
            print(f"Error updating datapoints for dataset: {dataset_name}")
        
        print(f"Dataset: {dataset_name} fetched successfully with {len(datapoints)} datapoints.")
        # print(datapoints)
    else:
        print(f"Dataset: {dataset_name} not found.")