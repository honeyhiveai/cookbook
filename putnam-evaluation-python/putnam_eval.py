import os
import json
from openai import OpenAI
from honeyhive.tracer import HoneyHiveTracer
from honeyhive.tracer.custom import trace
import honeyhive
from honeyhive.models import components

# Initialize HoneyHive client
hhai = honeyhive.HoneyHive(
    bearer_auth="YOUR_HONEYHIVE_API_KEY",  # <<<< REPLACE WITH YOUR HONEYHIVE API KEY >>>>
)

# Set up OpenAI API key
OPENAI_API_KEY = 'YOUR_OPENAI_API_KEY'  # <<<< REPLACE WITH YOUR OPENAI API KEY >>>>
os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY

# Initialize OpenAI client
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# Create a HoneyHive run for this evaluation
eval_run = hhai.runs.create_run(request=components.CreateRunRequest(
    project='YOUR_HONEYHIVE_PROJECT_NAME',  # <<<< REPLACE WITH YOUR HONEYHIVE PROJECT NAME >>>>
    name='o1-preview-eval',
    event_ids=[],
))

run_id = eval_run.create_run_response.run_id

# Function to load JSONL file
def load_jsonl(file_path):
    with open(file_path, 'r') as file:
        return [json.loads(line) for line in file]

# Load Putnam questions
script_path = os.path.abspath(__file__)
script_dir = os.path.dirname(script_path)
json_path = os.path.join(script_dir, 'putnam_2023.jsonl')
putnam_questions = load_jsonl(json_path)

# Function to generate response using OpenAI API
@trace()
def generate_response(question, ground_truth):
    completion = openai_client.chat.completions.create(
        model="o1-preview",
        messages=[
            {"role": "user", "content": question}
        ]
    )
    return completion.choices[0].message.content

# Function to process each question
@trace()
def process_question(question, ground_truth, question_id, category):
    result = generate_response(question, ground_truth)
    print(f"Question ID: {question_id}")
    print(f"Query: {question}")
    print(f"Response: {result}")
    print(f"Category: {category}")
    print("---")
    return result

# Main execution
if __name__ == "__main__":
    event_ids_eval = []

    for question_data in putnam_questions:
        # Initialize HoneyHive tracer for each question
        HoneyHiveTracer.init(
            api_key='YOUR_HONEYHIVE_API_KEY',  # <<<< REPLACE WITH YOUR HONEYHIVE API KEY >>>>
            project='YOUR_HONEYHIVE_PROJECT_NAME',  # <<<< REPLACE WITH YOUR HONEYHIVE PROJECT NAME >>>>
            source='evaluation',
            session_name=f'Putnam Q&A OpenAI - Question {question_data["question_id"]}'
        )

        # Set metadata for the current question
        HoneyHiveTracer.set_metadata({
            "run_id": run_id,
            "question_id": question_data["question_id"],
            "question": question_data["question"],
            "category": question_data["question_category"]
        })

        # Process the question
        process_question(
            question_data["question"], 
            question_data["solution"], 
            question_data["question_id"],
            question_data["question_category"]
        )
        event_ids_eval.append(HoneyHiveTracer.session_id)

    # Update the HoneyHive run with results
    hhai.runs.update_run(
        run_id,
        components.UpdateRunRequest(
            event_ids=event_ids_eval,
            status=components.UpdateRunRequestStatus.COMPLETED
        )
    )

    print("Putnam evaluation completed and pushed to HoneyHive.")