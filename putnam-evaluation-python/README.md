# Evaluating Advanced Reasoning Models on Putnam 2023

This tutorial will guide you through setting up and running an AI evaluation for Putnam 2023 competition questions using OpenAI's API and HoneyHive. The William Lowell Putnam Mathematical Competition is the preeminent mathematics competition for undergraduate college students in North America, known for its exceptionally challenging problems that test deep mathematical thinking and rigorous proof writing abilities.

This evaluation is particularly significant as it allows us to assess how well advanced language models like OpenAI's `o3-mini` or Deepseek's `R1` can handle complex mathematical reasoning and proof generation. The Putnam competition serves as an excellent benchmark due to its consistent difficulty level and requirement for both creative problem-solving and formal mathematical rigor. By evaluating model performance on these problems, we can better understand the current capabilities and limitations of AI systems in advanced mathematical reasoning.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Clone the Repository](#clone-the-repository)
3. [Setup Python Environment](#setup-python-environment)
4. [Install Required Packages](#install-required-packages)
5. [Configure API Keys and Project Settings](#configure-api-keys-and-project-settings)
6. [Prepare the Dataset](#prepare-the-dataset)
7. [Run the Evaluation](#run-the-evaluation)
8. [Reviewing the Results](#reviewing-the-results)
9. [Additional Notes](#additional-notes)

---

## 1. Prerequisites

Before you begin, make sure you have:

- **Python 3.10+** installed.
- An **OpenAI API key**. ([Get one here](https://platform.openai.com/account/api-keys))
- A **HoneyHive API key**, along with your **HoneyHive project name** and **dataset ID**.
- The Putnam 2023 questions and solutions in a JSONL file (e.g., `putnam_2023.jsonl`).

---

## 2. Clone the Repository

Open your terminal (or command prompt) and run the following commands:

```bash
git clone https://github.com/honeyhiveai/cookbook
cd putnam-evaluation-python
```

## 3. Setup Python Environment

Create and activate a virtual environment to keep your dependencies isolated:

```bash
# Create a virtual environment
python -m venv putnam_eval_env

# On macOS/Linux:
source putnam_eval_env/bin/activate

# On Windows:
putnam_eval_env\Scripts\activate
```

## 4. Install Required Packages

Install the necessary Python packages using the provided requirements.txt:

```bash
pip install -r requirements.txt
```

## 5. Configure API Keys and Project Settings

Open the putnam_eval.py script in your preferred text editor and update the following:

### Update OpenAI API Key

Replace 'YOUR_OPENAI_API_KEY' with your actual OpenAI API key in the script:

```python
# Set your OpenAI API key (anonymized in this example)
OPENAI_API_KEY = 'YOUR_OPENAI_API_KEY'
os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
```

### Update HoneyHive Configuration

In the if __name__ == "__main__": block at the bottom of the script, replace the placeholders with your HoneyHive credentials:

```python
if __name__ == "__main__":
    evaluate(
        function=putnam_qa,  # The main function to generate responses.
        hh_api_key='YOUR_HONEYHIVE_API_KEY',          # Replace with your HoneyHive API key.
        hh_project='YOUR_HONEYHIVE_PROJECT_NAME',       # Replace with your HoneyHive project name.
        dataset_id='YOUR_HONEYHIVE_DATASET_ID',         # Replace with your dataset ID.
        evaluators=[response_quality_evaluator]
    )
    print("Putnam evaluation completed and pushed to HoneyHive.")
```

**Important**: Keep your API keys confidential. Do not commit them to version control.

## 6. Prepare the Dataset

Upload your Putnam 2023 dataset to HoneyHive by following the guide at [https://docs.honeyhive.ai/datasets/import](https://docs.honeyhive.ai/datasets/import). The dataset should be in JSONL format containing the Putnam questions and their corresponding solutions.

## 7. Run the Evaluation

With everything configured, run the evaluation script from your terminal:

```bash
python putnam_eval.py
```

The script will:
- Load each question from your dataset.
- Generate a response using the OpenAI model.
- Trace and log metadata to HoneyHive.
- Evaluate the response quality using the built-in evaluator.

After running, you should see a confirmation message indicating that the evaluation has been pushed to HoneyHive.

## 8. Reviewing the Results

To review the evaluation results:

### Log into your HoneyHive Dashboard:
Go to HoneyHive and sign in.

### Navigate to the Evaluations Tab:
In your project, click on the `Experiments` tab to view the detailed traces and evaluation scores for each question.

## 9. Additional Notes

### Security:
Always keep your API keys secure. Avoid sharing or committing them to public repositories.

### Model Adjustments:
The script currently uses OpenAI's `o3-mini` model for generating responses and the "o3-mini" model for model-graded evaluation. Adjust these model names if necessary to suit your needs or available models. The choice of o3-mini for evaluation is particularly important as it represents one of the most advanced models for mathematical reasoning, making it well-suited for assessing solutions to complex Putnam problems.

### Customization:
You can modify the evaluation criteria or grading prompt in the script to better align with your specific evaluation standards. The current evaluation system is designed to mirror the rigorous grading standards of the actual Putnam Competition, where partial credit is awarded based on the completeness and correctness of the mathematical reasoning demonstrated.

By following these steps, you will have a fully functional evaluation system for Putnam competition questions integrated with HoneyHive's observability platform. This setup allows you to systematically assess how well AI models can handle some of the most challenging undergraduate mathematics problems, providing valuable insights into their mathematical reasoning capabilities. If you encounter any issues, please refer to the HoneyHive documentation or reach out to their support for further assistance.

Happy Evaluating!
