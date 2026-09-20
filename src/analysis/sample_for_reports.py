"""Select a deliberate sample of anomalies for phase 3 report generation.

Not all 14,230 flagged readings get a report. This picks the 5 known real
major events as core cases, plus a stratified sample across the other
series and severity levels for variety, roughly 25-30 total.
"""

import json
from pathlib import Path

import pandas as pd

PROCESSED_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"

SEED = 42
N_PER_SERIES_WITH_CORE = 2
N_PER_SERIES_WITHOUT_CORE = 3

KNOWN_EVENTS = [
    ("03451500", "00060", pd.Timestamp("2024-09-27 21:38:00", tz="UTC"), "Hurricane Helene, French Broad River"),
    ("08166200", "00060", pd.Timestamp("2025-07-04 11:45:00", tz="UTC"), "TX Hill Country flood, Guadalupe near Hunt"),
    ("08167000", "00060", pd.Timestamp("2025-07-04 16:00:00", tz="UTC"), "TX Hill Country flood, Guadalupe at Comfort"),
    ("01646500", "00060", pd.Timestamp("2025-05-16 02:00:00", tz="UTC"), "Potomac River peak flow"),
    ("04234000", "00060", pd.Timestamp("2025-03-06 15:00:00", tz="UTC"), "Fall Creek spring spike"),
]


def severity_tier(g: pd.DataFrame) -> pd.Series:
    band = (g["baseline_high"] - g["baseline_low"]).clip(lower=1e-9)
    dist = (g["value"] - g["baseline_high"]).clip(lower=0) + (g["baseline_low"] - g["value"]).clip(lower=0)
    score = dist / band
    q1, q2 = score.quantile([1 / 3, 2 / 3])
    tier = pd.cut(score, bins=[-1, q1, q2, score.max() + 1], labels=["borderline", "moderate", "severe"])
    return tier, score


def main() -> None:
    df = pd.DataFrame(json.loads((PROCESSED_DIR / "anomaly_context.json").read_text()))
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    core_records = []
    core_keys = set()
    for site_id, param_code, peak_ts, label in KNOWN_EVENTS:
        sub = df[(df["site_id"] == site_id) & (df["param_code"] == param_code)]
        nearest_idx = (sub["timestamp"] - peak_ts).abs().idxmin()
        rec = df.loc[nearest_idx].to_dict()
        rec["sample_reason"] = f"core_event: {label}"
        rec["severity_tier"] = "severe"
        core_records.append(rec)
        core_keys.add((rec["site_id"], rec["param_code"], rec["timestamp"]))

    core_site_params = {(e[0], e[1]) for e in KNOWN_EVENTS}
    all_site_params = set(zip(df["site_id"], df["param_code"]))

    extra_records = []
    for site_id, param_code in sorted(all_site_params):
        g = df[(df["site_id"] == site_id) & (df["param_code"] == param_code)].copy()
        g = g[~g["timestamp"].apply(lambda t: (site_id, param_code, t) in core_keys)]
        if g.empty:
            continue
        tier, score = severity_tier(g)
        g["severity_tier"] = tier
        g["severity_score"] = score

        n_target = N_PER_SERIES_WITH_CORE if (site_id, param_code) in core_site_params else N_PER_SERIES_WITHOUT_CORE
        per_tier = max(1, n_target // 3)
        picked = []
        for tier_name in ["borderline", "moderate", "severe"]:
            pool = g[g["severity_tier"] == tier_name]
            if pool.empty:
                continue
            picked.append(pool.sample(n=min(per_tier, len(pool)), random_state=SEED))
        combined = pd.concat(picked) if picked else g.sample(n=min(n_target, len(g)), random_state=SEED)
        combined = combined.head(n_target)
        for _, row in combined.iterrows():
            rec = row.to_dict()
            rec["sample_reason"] = "stratified_sample"
            extra_records.append(rec)

    for rec in core_records + extra_records:
        rec["timestamp"] = rec["timestamp"].isoformat() if isinstance(rec["timestamp"], pd.Timestamp) else rec["timestamp"]
        rec.pop("severity_score", None)

    sample = core_records + extra_records
    sample_df = pd.DataFrame(sample)

    print(f"=== sample composition: {len(sample)} total ({len(core_records)} core events, {len(extra_records)} stratified) ===")
    print(sample_df.groupby(["site_name", "param_code", "sample_reason"]).size().to_string())
    print()
    print("=== severity tier breakdown ===")
    print(sample_df["severity_tier"].value_counts().to_string())
    print()

    out_path = PROCESSED_DIR / "report_sample.json"
    out_path.write_text(json.dumps(sample, indent=2, default=str))
    print(f"wrote {out_path} ({len(sample)} records)")


if __name__ == "__main__":
    main()
