"""Use Drex as a judge in a HoneyHive experiment.

The evaluator asks Drex one yes/no question per datapoint and returns the probability that the
answer is supported by its context. Drex returns probabilities, so you can choose the pass
threshold after the run instead of before it.
"""

import os

from honeyhive import evaluate
from typesafe_sdk import Noul, TypeSafeClient

DATASET = [
    {
        "inputs": {
            "question": "When was the library founded?",
            "context": "The Riverside Library opened in 1923 and moved to its current building in 1968.",
        },
        "ground_truth": {"answer": "1923"},
    },
    {
        "inputs": {
            "question": "Does the library lend laptops?",
            "context": "Members can borrow up to ten books for three weeks. Study rooms need a booking.",
        },
        "ground_truth": {"answer": "The context does not say."},
    },
]

ANSWERS = {
    "When was the library founded?": "It opened in 1923.",
    "Does the library lend laptops?": "Yes, laptops can be borrowed for a week.",
}


def app(datapoint):
    """Stand-in for the application you are evaluating."""
    return {"answer": ANSWERS[datapoint["inputs"]["question"]]}


client = TypeSafeClient(model="drex-max", timeout=60)


def grounded(outputs, inputs, ground_truth=None):
    """Probability that every claim in the answer is supported by the context."""
    result = client.system_one(
        state={"question": inputs["question"], "context": inputs["context"], "answer": outputs["answer"]},
        questions={
            "grounded": Noul(instructions="Is every claim in the answer supported by the context?"),
        },
    )
    return result.nouls["grounded"].noul


evaluate(
    function=app,
    dataset=DATASET,
    evaluators=[grounded],
    api_key=os.environ["HH_API_KEY"],
    name="drex-grounded",
    max_workers=4,
)
