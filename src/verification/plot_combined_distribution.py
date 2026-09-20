"""Plot the combined system's effective trust score: Noul's P(faithful),
overridden to 0 whenever the deterministic entity check fails. Shows
whether the wrong_station cluster, which straddled the threshold under
Noul alone, is now fully separated.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

PROCESSED_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"
FIGURES_DIR = Path(__file__).resolve().parents[2] / "reports" / "figures"

THRESHOLD = 0.5

CATEGORY_ORDER = [
    "faithful",
    "wrong_station",
    "wrong_parameter",
    "wrong_value",
    "fabricated_cause",
    "fabricated_comparison",
]


def main() -> None:
    df = pd.read_csv(PROCESSED_DIR / "combined_eval.csv")
    df["category"] = df.apply(lambda r: "faithful" if not r["is_corrupted"] else r["error_type"], axis=1)
    df["effective_score"] = df.apply(lambda r: r["p_faithful"] if r["entity_check_passed"] else 0.0, axis=1)
    df["overridden"] = ~df["entity_check_passed"]

    rng = np.random.default_rng(0)
    fig, ax = plt.subplots(figsize=(9, 5))

    for i, cat in enumerate(CATEGORY_ORDER):
        sub = df[df["category"] == cat]
        if sub.empty:
            continue
        y = i + rng.uniform(-0.15, 0.15, size=len(sub))
        base_color = "#2b6cb0" if cat == "faithful" else "#c53030"
        not_overridden = sub[~sub["overridden"]]
        overridden = sub[sub["overridden"]]
        y_no = i + rng.uniform(-0.15, 0.15, size=len(not_overridden))
        y_ov = i + rng.uniform(-0.15, 0.15, size=len(overridden))
        ax.scatter(not_overridden["effective_score"], y_no, color=base_color, s=60, alpha=0.8, edgecolor="white", linewidth=0.5)
        if not overridden.empty:
            ax.scatter(
                overridden["effective_score"], y_ov, color=base_color, s=110, alpha=0.9,
                marker="X", edgecolor="black", linewidth=0.8,
                label="entity check override (Noul alone would have missed)" if i == CATEGORY_ORDER.index("wrong_station") else None,
            )

    ax.axvline(THRESHOLD, color="#4a5568", linestyle="--", linewidth=1, label=f"threshold {THRESHOLD}")
    ax.set_yticks(range(len(CATEGORY_ORDER)))
    ax.set_yticklabels([c.replace("_", " ") for c in CATEGORY_ORDER])
    ax.set_xlabel("effective trust score (Noul P(faithful), forced to 0 if the entity check fails)")
    ax.set_xlim(-0.05, 1.05)
    ax.set_title("Combined system: deterministic entity check + Noul faithfulness score")
    ax.legend(loc="lower right", fontsize=8)
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()

    out_path = FIGURES_DIR / "combined_distribution.png"
    fig.savefig(out_path, dpi=140)
    plt.close(fig)
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
