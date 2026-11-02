"""Trace a Drex decision-model call in HoneyHive.

Drex serves the same `POST /v1/systemone` as TypeSafe's Jev, so the `typesafe-sdk` client and its
OpenInference instrumentor work against it with a base URL, a key and an explicit model.
"""

import os

from honeyhive import HoneyHiveTracer
from openinference.instrumentation.typesafe import TypeSafeAIInstrumentor
from typesafe_sdk import Choice, Noul, Score, TypeSafeClient

tracer = HoneyHiveTracer.init(session_name="drex-support-triage")
TypeSafeAIInstrumentor().instrument(tracer_provider=tracer.provider)

# TYPESAFE_API_KEY and TYPESAFE_BASE_URL are read from the environment. A Drex model id is required:
# `jev-latest`, the SDK's default, is not a Drex model.
with TypeSafeClient(model="drex-max", timeout=60) as client:
    result = client.system_one(
        state={
            "ticket_id": "ORD-1003",
            "document": (
                "Order ORD-1003 was supposed to arrive last week and is "
                "still marked delayed. I need it today for an event."
            ),
        },
        questions={
            "shipping": Noul(instructions="Is this ticket about a shipment delay?"),
            "tone": Choice(
                instructions="What is the customer's tone?",
                criteria={"calm": None, "frustrated": None, "angry": None},
            ),
            "urgency": Score(
                instructions="How urgent is this ticket?",
                criteria=["can wait", "this week", "today"],
            ),
        },
    )

print("model:", result.model)
print("shipping delay (probability of yes):", result.nouls["shipping"].noul)
print("tone:", result.choices["tone"].choice, result.choices["tone"].confidence)
print("urgency:", result.scores["urgency"].score, result.scores["urgency"].confidence)

tracer.force_flush()
