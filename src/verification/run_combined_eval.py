"""Combine the deterministic entity-match check with the Noul faithfulness
score and re-evaluate the full 27-report sample honestly.

A report is flagged untrustworthy if EITHER the entity check fails OR
Noul's P(faithful) falls below the threshold. Reuses the Noul scores
already collected in data/processed/faithfulness_eval.csv rather than
re-calling the API, since the report text hasn't changed.
"""

from pathlib import Path

import pandas as pd

from src.verification.entity_check import check_entity_match

PROCESSED_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"
THRESHOLD = 0.5


def main() -> None:
    import json

    reports = {r["report_id"]: r for r in json.loads((PROCESSED_DIR / "reports.json").read_text())}
    scores = pd.read_csv(PROCESSED_DIR / "faithfulness_eval.csv")

    rows = []
    for _, row in scores.iterrows():
        rec = reports[row["report_id"]]
        entity = check_entity_match(rec["report_text"], rec["site_id"])
        p_faithful = row["p_faithful"]
        noul_flag = p_faithful < THRESHOLD
        entity_flag = not entity["passed"]
        combined_flag = noul_flag or entity_flag

        rows.append(
            {
                "report_id": row["report_id"],
                "site_id": rec["site_id"],
                "site_name": rec["site_name"],
                "is_corrupted": row["is_corrupted"],
                "error_type": row["error_type"],
                "p_faithful": p_faithful,
                "entity_check_passed": entity["passed"],
                "entity_check_reason": entity["reason"],
                "noul_flags_untrustworthy": noul_flag,
                "combined_flags_untrustworthy": combined_flag,
            }
        )

    df = pd.DataFrame(rows)
    out_path = PROCESSED_DIR / "combined_eval.csv"
    df.to_csv(out_path, index=False)

    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", None)

    print("=== entity check results, all 36 reports ===")
    print(df[["report_id", "site_id", "is_corrupted", "error_type", "entity_check_passed", "entity_check_reason"]].to_string(index=False))
    print()

    print("=== the two known wrong_station cases ===")
    ws = df[df["error_type"] == "wrong_station"]
    print(ws[["report_id", "p_faithful", "noul_flags_untrustworthy", "entity_check_passed", "combined_flags_untrustworthy"]].to_string(index=False))
    print()

    print("=== entity check false positives: faithful reports the entity check itself flags ===")
    ent_fp = df[(~df["is_corrupted"]) & (~df["entity_check_passed"])]
    if ent_fp.empty:
        print("none: the entity check passes all 27 faithful reports")
    else:
        print(ent_fp[["report_id", "site_name", "entity_check_reason"]].to_string(index=False))
    print()

    print(f"=== combined system confusion matrix (threshold {THRESHOLD}) ===")
    faithful = df[~df["is_corrupted"]]
    corrupted = df[df["is_corrupted"]]

    tp = faithful[~faithful["combined_flags_untrustworthy"]]
    fp = faithful[faithful["combined_flags_untrustworthy"]]
    tn = corrupted[corrupted["combined_flags_untrustworthy"]]
    fn = corrupted[~corrupted["combined_flags_untrustworthy"]]

    print(f"faithful reports total: {len(faithful)}")
    print(f"  correctly scored trustworthy (true positive): {len(tp)}")
    print(f"  WRONGLY flagged untrustworthy (false positive): {len(fp)}")
    if not fp.empty:
        print(fp[["report_id", "site_name", "p_faithful", "entity_check_passed"]].to_string(index=False))

    print(f"\ncorrupted reports total: {len(corrupted)}")
    print(f"  correctly flagged untrustworthy (true negative): {len(tn)}")
    print(f"  WRONGLY scored trustworthy, missed (false negative): {len(fn)}")
    if not fn.empty:
        print(fn[["report_id", "error_type", "p_faithful", "entity_check_passed"]].to_string(index=False))

    print("\n=== combined system, by error type ===")
    print(corrupted.groupby("error_type")["combined_flags_untrustworthy"].agg(["sum", "count"]).to_string())

    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
