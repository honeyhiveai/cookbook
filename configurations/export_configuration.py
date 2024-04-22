import requests
import os

HONEYHIVE_BASE_URL = "http://localhost:4785"
HH_API_KEY = os.environ.get('HH_API_KEY', 'API_KEY_HERE')


def get_configuration(project_name: str, configuration_name: str = None):
    headers = {"Authorization": f"Bearer {HH_API_KEY}"} 
    project_params = {"project_name": project_name}

    url = HONEYHIVE_BASE_URL + "/configurations"
    configuration_params = {
        'project_name': project_name
    }

    if configuration_name:
        configuration_params['name'] = configuration_name

    configurations = requests.request("GET", url, headers=headers, params=configuration_params)
    found = configurations.json()

    return found[0] if found else None

if __name__ == "__main__":
    project_name = "New Project"
    configuration_name = "production"
    configuration = get_configuration(project_name, configuration_name)
    if configuration:
        print(f"Configuration found: {configuration['name']}")
        print(configuration['parameters'])
