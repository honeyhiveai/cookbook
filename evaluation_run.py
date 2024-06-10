from dotenv import load_dotenv
import os
load_dotenv()

from evaluations.evaluation_template import start_evaluation, finish_evaluation, post_event_to_evaluation
from datasets.export_dataset import export_dataset
from template_pipelines.model_completion import run_pipeline

dataset_name = os.getenv('DATASET_NAME')
project_id = os.getenv('HH_PROJECT_ID')
# evaluation_name = os.getenv('EVALUATION_NAME')

sample_size = 1500
SYSTEM_PROMPT = "You are a helpful assistant. Answer the question below using Yes or No. If you are unsure, answer using your best judgment using Yes or No. Do not provide additional information."
USER_PROMPT = "{{question}}"

provider = "ollama"
model = "llama2"

evaluation_name = f"{provider} - {model} - {dataset_name}"

evaluation_config = {
    "provider": provider,
    "model": model,
}

# evaluators = ['ground_truth_match', 'tokens_per_second']
# eval_passing_ranges = {
#     'ground_truth_match': [3, 5],
#     'tokens_per_second': [10, 500]
# }

def run_evaluation(project_id, dataset, configuration, evaluation_name, dataset_name):
    # 1. Initialize evaluation
    evaluation_id = start_evaluation(
        project_id, 
        configuration,
        evaluation_name,
        dataset_name
        )

    # 2. Run evaluation on dataset
    event_ids = []
    session_ids = []
    datapoints = dataset['datapoints']

    for datapoint in datapoints:
        print(f"Running for datapoint: {str(datapoint)[:50]}...")
        ids_dict = run_pipeline(
            project_id,
            datapoint, 
            SYSTEM_PROMPT, 
            USER_PROMPT, 
            provider, 
            model,
            evaluation_id
        )
        
        # eval_status = check_eval_status(event_id, evaluators, eval_passing_ranges)

    # 4. Finish evaluation
    finish_evaluation(evaluation_id)

if __name__ == '__main__':
    dataset = export_dataset(
        dataset_name, 
        project_id,
        size=sample_size
        )
    # print(f"Dataset: {dataset}")
    if dataset:
        run_evaluation(
            project_id, 
            dataset, 
            evaluation_config,
            evaluation_name,
            dataset_name
            )
    else:
        print(f"Failed to run evaluation on dataset: {dataset_name} because dataset was null")
