"""Inspect the pulled NWIS data: counts, sampling frequency, gaps, and
per-station stats. Prints real numbers to the terminal and writes one
time series plot per station to reports/figures/.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

PROCESSED_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"
FIGURES_DIR = Path(__file__).resolve().parents[2] / "reports" / "figures"

PARAM_LABELS = {
    "00060": "Streamflow (cfs)",
    "00010": "Water temperature (C)",
}

GAP_THRESHOLD_MINUTES = 60


def summarize_group(g: pd.DataFrame) -> dict:
    g = g.sort_values("datetime")
    dt = g["datetime"]
    # Diff within each concurrent sensor (method_id) separately so an
    # interleaved second sensor does not produce spurious ~0min gaps.
    diffs_min = pd.concat(
        gm.sort_values("datetime")["datetime"].diff().dropna().dt.total_seconds() / 60
        for _, gm in g.groupby("method_id")
    )

    interval_counts = diffs_min.value_counts()
    top_intervals = interval_counts.head(3)
    top_intervals_str = ", ".join(
        f"{minutes:g}min x{count} ({100*count/len(diffs_min):.1f}%)"
        for minutes, count in top_intervals.items()
    )

    gaps = diffs_min[diffs_min > GAP_THRESHOLD_MINUTES]

    return {
        "site_id": g["site_id"].iloc[0],
        "site_name": g["site_name"].iloc[0],
        "param_code": g["param_code"].iloc[0],
        "n_methods": g["method_id"].nunique(),
        "n_readings": len(g),
        "first": dt.min(),
        "last": dt.max(),
        "top_intervals": top_intervals_str,
        "n_gaps_over_1h": len(gaps),
        "total_gap_time_hours": round(gaps.sum() / 60, 1) if len(gaps) else 0.0,
        "longest_gap_hours": round(gaps.max() / 60, 1) if len(gaps) else 0.0,
        "min_value": g["value"].min(),
        "max_value": g["value"].max(),
        "mean_value": g["value"].mean(),
        "median_value": g["value"].median(),
        "std_value": g["value"].std(),
    }


def flag_extremes(g: pd.DataFrame, z_thresh: float = 4.0) -> pd.DataFrame:
    mean = g["value"].mean()
    std = g["value"].std()
    if std == 0 or pd.isna(std):
        return g.iloc[0:0]
    z = (g["value"] - mean) / std
    return g[z.abs() >= z_thresh]


def plot_station(site_id: str, site_name: str, g_all_params: pd.DataFrame) -> Path:
    param_codes = sorted(g_all_params["param_code"].unique())
    fig, axes = plt.subplots(len(param_codes), 1, figsize=(11, 3.2 * len(param_codes)), sharex=False)
    if len(param_codes) == 1:
        axes = [axes]

    for ax, code in zip(axes, param_codes):
        g = g_all_params[g_all_params["param_code"] == code].sort_values("datetime")
        for method_id, gm in g.groupby("method_id"):
            label = gm["method_desc"].iloc[0] or f"method {method_id}"
            ax.plot(gm["datetime"], gm["value"], linewidth=0.6, label=label if g["method_id"].nunique() > 1 else None)
        extremes = flag_extremes(g)
        if not extremes.empty:
            ax.scatter(extremes["datetime"], extremes["value"], color="#c53030", s=14, zorder=5, label="|z| >= 4")
        if g["method_id"].nunique() > 1 or not extremes.empty:
            ax.legend(loc="upper right", fontsize=7)
        ax.set_ylabel(PARAM_LABELS.get(code, code))
        ax.set_title(f"{site_name} ({site_id}) - {PARAM_LABELS.get(code, code)}", fontsize=10)
        ax.grid(alpha=0.3)

    fig.tight_layout()
    out_path = FIGURES_DIR / f"{site_id}.png"
    fig.savefig(out_path, dpi=130)
    plt.close(fig)
    return out_path


def main() -> None:
    df = pd.read_parquet(PROCESSED_DIR / "readings.parquet")
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True)

    print(f"total rows: {len(df)}")
    print(f"date range pulled: {df['datetime'].min()} to {df['datetime'].max()}")
    print(f"stations: {df['site_id'].nunique()}, station-parameter series: {df.groupby(['site_id','param_code']).ngroups}")
    print()

    print("=== concurrent sensors under the same site-parameter (n_methods > 1) ===")
    for (site_id, param_code), g in df.groupby(["site_id", "param_code"]):
        methods = g[["method_id", "method_desc"]].drop_duplicates()
        if len(methods) > 1:
            site_name = g["site_name"].iloc[0]
            print(f"{site_id} ({site_name}) {param_code}: {len(methods)} concurrent methods")
            for _, m in methods.iterrows():
                n = (g["method_id"] == m["method_id"]).sum()
                print(f"    method {m['method_id']} \"{m['method_desc']}\": {n} readings")
    print()

    summaries = []
    for (site_id, param_code), g in df.groupby(["site_id", "param_code"]):
        summaries.append(summarize_group(g))

    summary_df = pd.DataFrame(summaries).sort_values(["site_name", "param_code"])
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", None)
    pd.set_option("display.max_colwidth", 60)

    print("=== per station-parameter: readings, sampling interval, gaps ===")
    cols = [
        "site_id", "param_code", "n_methods", "n_readings",
        "top_intervals", "n_gaps_over_1h", "total_gap_time_hours", "longest_gap_hours",
    ]
    print(summary_df[cols].to_string(index=False))
    print()

    print("=== value range and variability ===")
    cols2 = ["site_id", "site_name", "param_code", "min_value", "max_value", "mean_value", "median_value", "std_value"]
    print(summary_df[cols2].to_string(index=False))
    print()

    print("=== extreme readings (|z| >= 4 within each station-parameter series) ===")
    for (site_id, param_code), g in df.groupby(["site_id", "param_code"]):
        extremes = flag_extremes(g)
        site_name = g["site_name"].iloc[0]
        param_name = g["param_name"].iloc[0]
        if extremes.empty:
            print(f"{site_id} {param_name}: none")
            continue
        peak = extremes.loc[extremes["value"].abs().idxmax()]
        print(
            f"{site_id} ({site_name}) {param_name}: {len(extremes)} extreme readings, "
            f"peak value {peak['value']} at {peak['datetime']}"
        )
    print()

    print("=== negative streamflow readings (tidal backflow or sensor artifact) ===")
    neg = df[(df["param_code"] == "00060") & (df["value"] < 0)]
    if neg.empty:
        print("none")
    else:
        for site_id, g in neg.groupby("site_id"):
            site_name = g["site_name"].iloc[0]
            print(f"{site_id} ({site_name}): {len(g)} negative readings, min {g['value'].min()}, "
                  f"range {g['datetime'].min()} to {g['datetime'].max()}")
    print()

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    print("=== writing plots ===")
    for site_id, g_site in df.groupby("site_id"):
        site_name = g_site["site_name"].iloc[0]
        path = plot_station(site_id, site_name, g_site)
        print(f"wrote {path}")

    summary_df.to_csv(PROCESSED_DIR / "station_summary.csv", index=False)
    print(f"\nwrote {PROCESSED_DIR / 'station_summary.csv'}")


if __name__ == "__main__":
    main()
