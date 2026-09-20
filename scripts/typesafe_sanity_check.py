"""Sanity check: confirm the Typesafe/Noul faithfulness checker works from
this repo's own venv before the reporting pipeline is built around it.

Requires TYPESAFE_API_KEY to be set in the environment. Never hardcode the
key in this file or any committed file.
"""

import os

from typesafe_sdk import Noul, TypeSafeClient

if not os.environ.get("TYPESAFE_API_KEY"):
    raise SystemExit("TYPESAFE_API_KEY is not set in the environment")

with TypeSafeClient() as client:
    response = client.system_one(
        state={
            "question": "What was the peak streamflow during the flood?",
            "retrieved_context": (
                "Streamflow at Guadalupe Rv at Kerrville, TX rose from a "
                "baseline near 2 cfs to a peak of 298000 cfs on 2025-07-04."
            ),
            "generated_answer": (
                "The peak streamflow during the flood was approximately "
                "298000 cfs."
            ),
        },
        questions={
            "faithful": Noul(
                instructions=(
                    "Is the generated answer faithful to the retrieved "
                    "context? A faithful answer is fully supported by the "
                    "context and does not add, contradict, or invent facts "
                    "not present in it."
                ),
            ),
        },
    )

print("model:", response.model)
print("P(faithful):", response.nouls["faithful"].noul)
