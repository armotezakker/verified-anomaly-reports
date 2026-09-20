"""Flag-rate sanity check: zoom into a representative, non-event period for
the highest-rate series and look at flagged points by eye against ordinary
day-to-day variability, before trusting the detector to feed phase 3.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from src.detection.rolling_iqr import DetectorConfig, detect

PROCESSED_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"
FIGURES_DIR = Path(__file__).resolve().parents[2] / "reports" / "figures"

# (site_id, param_code, label, known event window to exclude from picking a
# "representative" week)
SERIES_TO_CHECK = [
    ("03451500", "00060", "French Broad River, streamflow", ("2024-09-20", "2024-10-10")),
    ("04234000", "00060", "Fall Creek, streamflow", ("2025-03-01", "2025-03-12")),
]


def main() -> None:
    df = pd.read_parquet(PROCESSED_DIR / "readings.parquet")
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True)

    for site_id, param_code, label, exclude_window in SERIES_TO_CHECK:
        g = df[(df["site_id"] == site_id) & (df["param_code"] == param_code)]
        g = g.sort_values("datetime").drop_duplicates("datetime")
        s = pd.Series(g["value"].values, index=pd.DatetimeIndex(g["datetime"]))

        result = detect(s, DetectorConfig(), floor=0.0)

        weekly = result["is_anomaly"].resample("7D").sum()
        excl_start, excl_end = pd.Timestamp(exclude_window[0], tz="UTC"), pd.Timestamp(exclude_window[1], tz="UTC")
        weekly_non_event = weekly[(weekly.index < excl_start) | (weekly.index > excl_end)]

        print(f"=== {label} ({site_id}) weekly flag counts, excluding {exclude_window} ===")
        print(weekly_non_event.to_string())

        nonzero = weekly_non_event[weekly_non_event > 0]
        print(
            f"{(weekly_non_event == 0).sum()} of {len(weekly_non_event)} non-event weeks have zero flags, "
            f"flags come in bursts across {len(nonzero)} weeks, not scattered evenly"
        )
        median_nonzero = nonzero.median()
        pick = (nonzero - median_nonzero).abs().idxmin()
        print(f"median flag count among weeks that have any flags: {median_nonzero}")
        print(f"picked representative burst week starting {pick} ({int(weekly_non_event.loc[pick])} flags that week)")
        print()

        window_start = pick - pd.Timedelta(days=3)
        window_end = pick + pd.Timedelta(days=10)
        window = result.loc[window_start:window_end]

        fig, ax = plt.subplots(figsize=(12, 4))
        ax.plot(window.index, window["value"], linewidth=0.9, color="#2b6cb0", label="value")
        ax.plot(window.index, window["baseline_median"], linewidth=0.8, color="#718096", alpha=0.7, label="trailing 14d median")
        ax.fill_between(window.index, window["baseline_low"], window["baseline_high"], color="#a0aec0", alpha=0.25, label="normal range")
        flagged = window[window["is_anomaly"]]
        if not flagged.empty:
            ax.scatter(flagged.index, flagged["value"], color="#c53030", s=22, zorder=5, label="flagged")
        ax.set_title(f"{label} - representative two-week window starting {pick.date()}", fontsize=10)
        ax.set_ylabel("value")
        ax.legend(loc="upper right", fontsize=8)
        ax.grid(alpha=0.3)
        fig.tight_layout()
        out_path = FIGURES_DIR / f"sanity_check_{site_id}_{param_code}.png"
        fig.savefig(out_path, dpi=140)
        plt.close(fig)
        print(f"wrote {out_path}")
        print()


if __name__ == "__main__":
    main()
