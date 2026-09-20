"""Plot P(faithful) split by faithful vs corrupted, and by error type,
to show by eye whether the checker actually separates the two groups.
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
    df = pd.read_csv(PROCESSED_DIR / "faithfulness_eval.csv")
    df["category"] = df.apply(lambda r: "faithful" if not r["is_corrupted"] else r["error_type"], axis=1)

    rng = np.random.default_rng(0)
    fig, ax = plt.subplots(figsize=(9, 5))

    for i, cat in enumerate(CATEGORY_ORDER):
        sub = df[df["category"] == cat]
        if sub.empty:
            continue
        y = i + rng.uniform(-0.15, 0.15, size=len(sub))
        color = "#2b6cb0" if cat == "faithful" else "#c53030"
        ax.scatter(sub["p_faithful"], y, color=color, s=60, alpha=0.8, edgecolor="white", linewidth=0.5)

    ax.axvline(THRESHOLD, color="#4a5568", linestyle="--", linewidth=1, label=f"threshold {THRESHOLD}")
    ax.set_yticks(range(len(CATEGORY_ORDER)))
    ax.set_yticklabels([c.replace("_", " ") for c in CATEGORY_ORDER])
    ax.set_xlabel("P(faithful)")
    ax.set_xlim(-0.05, 1.05)
    ax.set_title("Faithfulness checker score by group: faithful reports vs each injected error type")
    ax.legend(loc="lower right", fontsize=8)
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()

    out_path = FIGURES_DIR / "faithfulness_distribution.png"
    fig.savefig(out_path, dpi=140)
    plt.close(fig)
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
