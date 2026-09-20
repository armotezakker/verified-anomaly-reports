"""Run the rolling IQR detector across all six station-parameter series,
report counts and known-event recall honestly, package minimal anomaly
context for phase 3, and write an anomaly log plus overlay plots.
"""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from src.detection.rolling_iqr import DetectorConfig, detect

PROCESSED_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"
FIGURES_DIR = Path(__file__).resolve().parents[2] / "reports" / "figures"

PARAM_LABELS = {
    "00060": "Streamflow (cfs)",
    "00010": "Water temperature (C)",
}

STATION_LOCATIONS = {
    "03451500": (35.60888889, -82.5780556),
    "08166200": (30.053266, -99.163375),
    "08167000": (29.96523889, -98.8971667),
    "01646500": (38.94977778, -77.12763889),
    "11447650": (38.45566389, -121.5016167),
    "04234000": (42.4533333, -76.47277778),
}

# Known real events found by inspection in phase 1, used only to check
# whether this simple detector actually catches them. site_id, param_code,
# the approximate peak timestamp (UTC), and a short label for reporting.
KNOWN_EVENTS = [
    ("03451500", "00060", pd.Timestamp("2024-09-27 21:38:00", tz="UTC"), "Hurricane Helene, French Broad River"),
    ("08166200", "00060", pd.Timestamp("2025-07-04 11:45:00", tz="UTC"), "TX Hill Country flood, Guadalupe near Hunt"),
    ("08167000", "00060", pd.Timestamp("2025-07-04 16:00:00", tz="UTC"), "TX Hill Country flood, Guadalupe at Comfort"),
    ("01646500", "00060", pd.Timestamp("2025-05-16 02:00:00", tz="UTC"), "Potomac River peak flow"),
    ("04234000", "00060", pd.Timestamp("2025-03-06 15:00:00", tz="UTC"), "Fall Creek spring spike"),
]


def resolve_sacramento_dual_sensor(df: pd.DataFrame) -> pd.DataFrame:
    """Sacramento water temperature (11447650, 00010) is reported by two
    concurrent sensors under the same parameter code. Phase 1 showed they
    track each other closely, so we average by timestamp: this uses both
    sensors when both reported at that tick and falls back to whichever one
    reported when only one did, rather than treating them as two
    independent series or arbitrarily dropping one.
    """
    mask = (df["site_id"] == "11447650") & (df["param_code"] == "00010")
    dual = df[mask]
    rest = df[~mask]

    n_ticks = dual["datetime"].nunique()
    n_both = dual.groupby("datetime")["method_id"].nunique()
    n_both_count = int((n_both == 2).sum())
    print(
        f"Sacramento temperature dual sensor: {n_ticks} distinct timestamps, "
        f"{n_both_count} ({100 * n_both_count / n_ticks:.1f}%) have both sensors, "
        f"{n_ticks - n_both_count} have only one"
    )

    collapsed = (
        dual.groupby(["site_id", "site_name", "param_code", "param_name", "datetime"], as_index=False)["value"]
        .mean()
    )
    return pd.concat([rest, collapsed], ignore_index=True, sort=False)


def main() -> None:
    df = pd.read_parquet(PROCESSED_DIR / "readings.parquet")
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True)

    print("=== resolving known data quality issues before detection ===")
    df = resolve_sacramento_dual_sensor(df)
    print(
        "Mixed 5-min/15-min sampling (French Broad, Guadalupe, Potomac): handled by using a "
        "time-based rolling window (see src/detection/rolling_iqr.py) rather than a fixed row "
        "count, so the baseline always covers the same trailing wall-clock span regardless of "
        "local sampling density. No resampling or interpolation of the raw values."
    )
    print()

    config = DetectorConfig()
    anomaly_rows = []
    counts = []

    for (site_id, param_code), g in df.groupby(["site_id", "param_code"]):
        g = g.sort_values("datetime").drop_duplicates("datetime")
        s = pd.Series(g["value"].values, index=pd.DatetimeIndex(g["datetime"]))
        floor = 0.0 if param_code == "00060" else None
        result_unfloored = detect(s, config, floor=None)
        result = detect(s, config, floor=floor)

        site_name = g["site_name"].iloc[0]
        param_name = g["param_name"].iloc[0]
        lat, lon = STATION_LOCATIONS[site_id]

        n_anom = int(result["is_anomaly"].sum())
        n_anom_unfloored = int(result_unfloored["is_anomaly"].sum())
        n_scored = int(result["has_baseline"].sum())
        counts.append(
            {
                "site_id": site_id,
                "site_name": site_name,
                "param_code": param_code,
                "n_readings": len(s),
                "n_scored": n_scored,
                "n_anomalies_unfloored": n_anom_unfloored,
                "n_anomalies": n_anom,
                "n_anomalies_added_by_floor": n_anom - n_anom_unfloored,
                "pct_anomalies_of_scored": round(100 * n_anom / n_scored, 3) if n_scored else None,
            }
        )

        for ts, row in result[result["is_anomaly"]].iterrows():
            anomaly_rows.append(
                {
                    "site_id": site_id,
                    "site_name": site_name,
                    "latitude": lat,
                    "longitude": lon,
                    "param_code": param_code,
                    "param_name": param_name,
                    "timestamp": ts.isoformat(),
                    "value": float(row["value"]),
                    "baseline_median": float(row["baseline_median"]),
                    "baseline_low": float(row["baseline_low"]),
                    "baseline_high": float(row["baseline_high"]),
                }
            )

        result.attrs["site_name"] = site_name
        _plot_series(site_id, site_name, param_code, param_name, result)

    counts_df = pd.DataFrame(counts).sort_values(["site_name", "param_code"])
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", None)

    print("=== anomaly counts per series (with zero-floor fix on streamflow) ===")
    print(counts_df.to_string(index=False))
    total_unfloored = counts_df["n_anomalies_unfloored"].sum()
    total_floored = counts_df["n_anomalies"].sum()
    total_scored = counts_df["n_scored"].sum()
    print(
        f"\ntotal: {total_unfloored} anomalies before the floor fix, {total_floored} after "
        f"({total_floored - total_unfloored} added by flooring streamflow lower bound at zero), "
        f"{total_floored}/{total_scored} = {100*total_floored/total_scored:.2f}% overall"
    )
    print()

    print("=== known real events: caught or missed ===")
    anomalies_df = pd.DataFrame(anomaly_rows)
    anomalies_df["timestamp"] = pd.to_datetime(anomalies_df["timestamp"])
    for site_id, param_code, peak_ts, label in KNOWN_EVENTS:
        sub = anomalies_df[(anomalies_df["site_id"] == site_id) & (anomalies_df["param_code"] == param_code)]
        if sub.empty:
            print(f"MISSED: {label} ({site_id}) - no anomalies flagged on this series at all")
            continue
        window = sub[(sub["timestamp"] >= peak_ts - pd.Timedelta(hours=6)) & (sub["timestamp"] <= peak_ts + pd.Timedelta(hours=6))]
        if not window.empty:
            print(f"CAUGHT: {label} ({site_id}) - {len(window)} flagged points within 6h of the known peak at {peak_ts}")
        else:
            nearest = sub.iloc[(sub["timestamp"] - peak_ts).abs().argsort()[:1]]
            gap = (nearest["timestamp"].iloc[0] - peak_ts)
            print(f"MISSED: {label} ({site_id}) - nearest flagged point is {gap} away from the known peak at {peak_ts}")
    print()

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    anomalies_df.to_csv(PROCESSED_DIR / "anomalies.csv", index=False)
    print(f"wrote {PROCESSED_DIR / 'anomalies.csv'} ({len(anomalies_df)} rows)")

    context_path = PROCESSED_DIR / "anomaly_context.json"
    context_path.write_text(json.dumps(anomaly_rows, indent=2))
    print(f"wrote {context_path} ({len(anomaly_rows)} records)")


def _plot_series(site_id, site_name, param_code, param_name, result: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(11, 3.5))
    ax.plot(result.index, result["value"], linewidth=0.6, color="#2b6cb0", label="value")
    ax.plot(result.index, result["baseline_median"], linewidth=0.6, color="#718096", alpha=0.6, label="trailing median")
    ax.fill_between(result.index, result["baseline_low"], result["baseline_high"], color="#a0aec0", alpha=0.2, label="normal range")
    flagged = result[result["is_anomaly"]]
    if not flagged.empty:
        ax.scatter(flagged.index, flagged["value"], color="#c53030", s=10, zorder=5, label="flagged")
    ax.set_title(f"{site_name} ({site_id}) - {PARAM_LABELS.get(param_code, param_code)}", fontsize=10)
    ax.set_ylabel(PARAM_LABELS.get(param_code, param_code))
    ax.legend(loc="upper right", fontsize=7)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    out_path = FIGURES_DIR / f"{site_id}_{param_code}_anomalies.png"
    fig.savefig(out_path, dpi=130)
    plt.close(fig)


if __name__ == "__main__":
    main()
