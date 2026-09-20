"""Generate one incident report per sampled anomaly, then deliberately
corrupt roughly a third of them with one labeled error each, to build the
test set for the faithfulness checker.

Requires ANTHROPIC_API_KEY in the environment. Never hardcoded here or
written to any file in this repo.
"""

import json
import os
import random
from pathlib import Path

import anthropic

from src.generation.prompts import CORRUPTION_INSTRUCTIONS, REPORT_SYSTEM_PROMPT, format_context

PROCESSED_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"
MODEL = "claude-haiku-4-5-20251001"
SEED = 7

if not os.environ.get("ANTHROPIC_API_KEY"):
    raise SystemExit("ANTHROPIC_API_KEY is not set in the environment")

client = anthropic.Anthropic()


def generate_report(record: dict) -> str:
    context = format_context(record)
    resp = client.messages.create(
        model=MODEL,
        max_tokens=300,
        system=REPORT_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": context}],
    )
    return resp.content[0].text.strip()


def corrupt_report(report_text: str, error_type: str) -> str:
    instruction = CORRUPTION_INSTRUCTIONS[error_type]
    resp = client.messages.create(
        model=MODEL,
        max_tokens=300,
        messages=[{"role": "user", "content": f"{instruction}\n\nReport:\n{report_text}"}],
    )
    return resp.content[0].text.strip()


def main() -> None:
    sample = json.loads((PROCESSED_DIR / "report_sample.json").read_text())

    print(f"generating {len(sample)} faithful reports with model {MODEL} ...")
    reports = []
    for i, record in enumerate(sample):
        report_id = f"r{i+1:02d}"
        text = generate_report(record)
        reports.append(
            {
                "report_id": report_id,
                **record,
                "report_text": text,
                "is_corrupted": False,
                "error_type": None,
                "original_report_id": report_id,
            }
        )
        print(f"  {report_id} [{record['site_name']}, {record['param_code']}, {record['severity_tier']}]: {text[:80]}...")

    rng = random.Random(SEED)
    error_types = list(CORRUPTION_INSTRUCTIONS.keys())
    n_corrupt = max(1, round(len(reports) / 3))
    plan = (error_types * ((n_corrupt // len(error_types)) + 1))[:n_corrupt]
    rng.shuffle(plan)

    indices = list(range(len(reports)))
    rng.shuffle(indices)
    chosen_indices = indices[:n_corrupt]

    print(f"\ncorrupting {n_corrupt} of {len(reports)} reports, one error type each ...")
    corrupted = []
    for idx, error_type in zip(chosen_indices, plan):
        base = reports[idx]
        corrupted_text = corrupt_report(base["report_text"], error_type)
        corrupted_id = f"{base['report_id']}_corrupt"
        corrupted.append(
            {
                **{k: v for k, v in base.items() if k not in ("report_text", "is_corrupted", "error_type", "original_report_id", "report_id")},
                "report_id": corrupted_id,
                "report_text": corrupted_text,
                "is_corrupted": True,
                "error_type": error_type,
                "original_report_id": base["report_id"],
            }
        )
        print(f"  {corrupted_id} [{error_type}]: {corrupted_text[:80]}...")

    all_records = reports + corrupted
    out_path = PROCESSED_DIR / "reports.json"
    out_path.write_text(json.dumps(all_records, indent=2))
    print(f"\nwrote {out_path} ({len(reports)} faithful, {len(corrupted)} corrupted, {len(all_records)} total)")


if __name__ == "__main__":
    main()
