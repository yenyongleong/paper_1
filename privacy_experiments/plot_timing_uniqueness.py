"""
Timing-channel uniqueness figure.

Reads results_*.json and produces fig2_timing_uniqueness.png:
  left panel  -- r(degree, query work): TCM / GSS / Scube on both datasets
  right panel -- P@100 on hub recovery via timing alone

Answers the reviewer question "why not use GSS?" by showing that TCM and GSS
are fine on the timing channel (r = 0, P@100 = chance) while Scube's
skew-aware allocation makes it the unique source of timing leakage.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mpl

mpl.rcParams.update({
    "figure.dpi": 110,
    "savefig.dpi": 180,
    "font.size": 11,
    "axes.grid": True,
    "grid.alpha": 0.3,
})

COLORS   = {"TCM": "#1f77b4", "GSS": "#2ca02c", "Scube": "#d62728"}
SCHEMES  = ["TCM", "GSS", "Scube"]
DATASETS = ["stackoverflow", "wiki-talk"]

ROOT    = Path(__file__).resolve().parent
RES_DIR = ROOT / "results"
FIG_DIR = ROOT / "figures"; FIG_DIR.mkdir(exist_ok=True, parents=True)


def load_metric(metric_fn):
    out = {s: [] for s in SCHEMES}
    for ds in DATASETS:
        with (RES_DIR / f"results_{ds}.json").open() as f:
            r = json.load(f)
        for s in SCHEMES:
            out[s].append(metric_fn(r["sketches"][s]))
    return out


def grouped_bars(ax, data, title, ylabel, ymax=None, annotate_fmt="{:.3f}"):
    x = np.arange(len(DATASETS))
    w = 0.26
    for i, s in enumerate(SCHEMES):
        bars = ax.bar(x + (i - 1) * w, data[s], w,
                      color=COLORS[s], edgecolor="#222", linewidth=1.0,
                      label=s)
        for b, v in zip(bars, data[s]):
            ax.text(b.get_x() + b.get_width() / 2,
                    b.get_height() + (ymax or 1.0) * 0.015,
                    annotate_fmt.format(v),
                    ha="center", va="bottom", fontsize=9)
    ax.set_xticks(x)
    ax.set_xticklabels(DATASETS)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    if ymax is not None:
        ax.set_ylim(0, ymax)
    ax.legend(loc="upper left", fontsize=9)
    ax.axhline(0, color="#444", linewidth=0.6)


def main():
    r_data = load_metric(lambda sk: sk["timing"]["pearson_r"])
    p_data = load_metric(lambda sk: sk["timing"]["precision_at_100_by_timing"])

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.0, 4.8))

    grouped_bars(ax1, r_data,
                 title="Correlation: true degree vs. per-query work",
                 ylabel="Pearson $r(d_v, \\mathrm{cells\\ probed})$",
                 ymax=1.15, annotate_fmt="{:+.3f}")
    ax1.axhline(0.5, linestyle=":", color="#888", linewidth=1,
                label="weak-correlation line")
    # mark the danger region
    ax1.axhspan(0.9, 1.15, alpha=0.08, color="red")
    ax1.text(1.4, 1.06, "near-perfect leakage", fontsize=9,
             color="#b31217", ha="right", style="italic")

    grouped_bars(ax2, p_data,
                 title="Timing-only attack: recovery of true top-100 hubs",
                 ylabel="Precision@100 (timing channel only)",
                 ymax=1.15, annotate_fmt="{:.2f}")
    ax2.axhline(0.5, linestyle=":", color="#888", linewidth=1)
    ax2.axhspan(0.9, 1.15, alpha=0.08, color="red")
    ax2.text(1.4, 1.06, "adversary wins", fontsize=9,
             color="#b31217", ha="right", style="italic")

    fig.suptitle("Timing side-channel is unique to skew-aware Scube; "
                 "TCM and GSS leak at chance levels",
                 y=1.02, fontsize=13)
    fig.tight_layout()
    out = FIG_DIR / "fig2_timing_uniqueness.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {out}")

    # also print numeric table for the paper caption
    print("\n--- numeric values (from results_*.json) ---")
    for metric, data, fmt in [("r(deg, work)", r_data, "{:+.4f}"),
                              ("P@100 timing",  p_data, "{:.3f}")]:
        print(f"{metric}:")
        for s in SCHEMES:
            vals = ", ".join(f"{ds}={fmt.format(v)}"
                             for ds, v in zip(DATASETS, data[s]))
            print(f"  {s:5s}: {vals}")


if __name__ == "__main__":
    main()
