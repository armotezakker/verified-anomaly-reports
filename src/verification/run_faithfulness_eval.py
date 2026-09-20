"""Run every generated report, faithful and deliberately corrupted, through
the Typesafe/Noul faithfulness checker and evaluate honestly whether it
separates the two groups.

Requires TYPESAFE_API_KEY in the environment.
"""

import json
import os
import time
from pathlib import Path

import pandas as pd
from typesafe_sdk import Noul, TypeSafeClient

from src.generation.prompts import format_context

PROCESSED_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"
THRESHOLD = 0.5

FAITHFUL_INSTRUCTIONS = (
    "Is the generated answer faithful to the retrieved context? A faithful answer is fully "
    "supported by the context and does not add, contradict, or invent facts not present in it."
)

if not os.environ.get("TYPESAFE_API_KEY"):
    raise SystemExit("TYPESAFE_API_KEY is not set in the environment")


def main() -> None:
    records = json.loads((PROCESSED_DIR / "reports.json").read_text())

    results = []
    with TypeSafeClient() as client:
        for rec in records:
            context = format_context(rec)
            response = client.system_one(
                state={
                    "question": "Is this incident report faithful to the sensor data it should be based on?",
                    "retrieved_context": context,
                    "generated_answer": rec["report_text"],
                },
                questions={"faithful": Noul(instructions=FAITHFUL_INSTRUCTIONS)},
            )
            p_faithful = response.nouls["faithful"].noul
            results.append(
                {
                    "report_id": rec["report_id"],
                    "site_name": rec["site_name"],
                    "param_code": rec["param_code"],
                    "is_corrupted": rec["is_corrupted"],
                    "error_type": rec["error_type"],
                    "p_faithful": p_faithful,
                }
            )
            print(f"{rec['report_id']:12s} corrupted={rec['is_corrupted']!s:5s} error={str(rec['error_type']):22s} P(faithful)={p_faithful:.3f}")
            time.sleep(0.1)

    df = pd.DataFrame(results)
    out_path = PROCESSED_DIR / "faithfulness_eval.csv"
    df.to_csv(out_path, index=False)
    print(f"\nwrote {out_path}")

    print("\n=== summary: P(faithful) by group ===")
    print(df.groupby("is_corrupted")["p_faithful"].describe().to_string())

    print("\n=== summary: P(faithful) by error type (corrupted only) ===")
    print(df[df["is_corrupted"]].groupby("error_type")["p_faithful"].describe().to_string())

    print(f"\n=== classification at threshold {THRESHOLD} ===")
    df["predicted_faithful"] = df["p_faithful"] >= THRESHOLD
    false_positives = df[(~df["is_corrupted"]) & (~df["predicted_faithful"])]
    false_negatives = df[(df["is_corrupted"]) & (df["predicted_faithful"])]
    true_positives = df[(~df["is_corrupted"]) & (df["predicted_faithful"])]
    true_negatives = df[(df["is_corrupted"]) & (~df["predicted_faithful"])]

    print(f"faithful reports total: {(~df['is_corrupted']).sum()}")
    print(f"  correctly scored faithful (true positive): {len(true_positives)}")
    print(f"  WRONGLY scored unfaithful (false positive): {len(false_positives)}")
    if not false_positives.empty:
        print(false_positives[["report_id", "site_name", "param_code", "p_faithful"]].to_string(index=False))

    print(f"\ncorrupted reports total: {df['is_corrupted'].sum()}")
    print(f"  correctly scored unfaithful (true negative): {len(true_negatives)}")
    print(f"  WRONGLY scored faithful (false negative, missed): {len(false_negatives)}")
    if not false_negatives.empty:
        print(false_negatives[["report_id", "error_type", "site_name", "p_faithful"]].to_string(index=False))

    print("\n=== hardest error types to catch (highest mean P(faithful) among corrupted) ===")
    print(df[df["is_corrupted"]].groupby("error_type")["p_faithful"].mean().sort_values(ascending=False).to_string())


if __name__ == "__main__":
    main()
