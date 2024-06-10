import requests
from dotenv import load_dotenv
import os

hh_api_key = os.getenv('HH_API_KEY')
headers = {
  "Authorization": f"Bearer {hh_api_key}",
  "Content-Type": "application/json"
}

def update_datapoints(dataset_name, datapoints, dataset_id):
  url = f'http://localhost:4785/datasets'
  data = {
    "dataset_id": dataset_id,
    "datapoints": datapoints
  }

  try:
    response = requests.put(url, headers=headers, json=data)
    response.raise_for_status()
    print(f"Datapoints updated successfully for dataset: {dataset_name}")
    return response.json()
  except requests.exceptions.HTTPError as http_err:
    print(f"HTTP error occurred while updating datapoints: {http_err}")
    return None
  except Exception as err:
    print(f"An unexpected error occurred while updating datapoints: {err}")
    return None