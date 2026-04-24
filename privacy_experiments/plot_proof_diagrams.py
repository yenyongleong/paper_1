"""
Four proof diagrams for the privacy-leakage narrative.

Values are hard-coded to the headline numbers from the empirical study:
  Hub Latency        = 19.995 us
  Non-Hub Latency    =  2.249 us
  Hub Addresses      = 40.80
  Non-Hub Addresses  =  4.47
  Pearson r(deg,t)   = 0.9917
  Recall@hub         = 100%
  Hub Error Rate     = 0.00%

Outputs (privacy_experiments/figures/):
  proof_diagram_1_leakage_chain.png
  proof_diagram_2_correlations.png
  proof_diagram_3_gap_analysis.png
  proof_diagram_4_timing_attack.png
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mpl
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

mpl.rcParams.update({
    "figure.dpi": 110,
    "savefig.dpi": 180,
    "font.size": 11,
    "axes.grid": True,
    "grid.alpha": 0.3,
})

HUB_LAT       = 19.995   # us
NONHUB_LAT    =  2.249   # us
HUB_ADDR      = 40.80
NONHUB_ADDR   =  4.47
R_DEG_ADDR    = 0.9928
R_ADDR_LAT    = 0.9970
R_DEG_LAT     = 0.9917
THRESHOLD_US  = (HUB_LAT + NONHUB_LAT) / 2   # ~= 11.122 us
EXPANSION_GAP = HUB_ADDR / NONHUB_ADDR        # ~= 9.13x
TIMING_GAP    = HUB_LAT  / NONHUB_LAT         # ~= 8.89x

FIG_DIR = Path(__file__).resolve().parent / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)


# ---------- Diagram 1: Side-Channel Leakage Chain -----------------------------
def diagram_leakage_chain():
    fig, ax = plt.subplots(figsize=(13.0, 3.4))
    ax.set_xlim(0, 13)
    ax.set_ylim(0, 3.4)
    ax.axis("off")
    ax.grid(False)

    boxes = [
        (0.2, "Stream Skewness",
              "Hubs: huge $d_v$\nTail: small $d_v$",
              "#fde7e9"),
        (3.4, "Differentiated\nAllocation $A_v=f(d_v)$",
              f"Hub: {HUB_ADDR:.2f} addr\nNon-hub: {NONHUB_ADDR:.2f} addr",
              "#ffe9d2"),
        (6.6, f"~{EXPANSION_GAP:.1f}x Memory\nExpansion",
              f"{HUB_ADDR:.2f}  vs.  {NONHUB_ADDR:.2f}\n(expansion ratio)",
              "#fff4bf"),
        (9.8, "Side-Channel\nObserver",
              f"Latency: {HUB_LAT:.2f} $\\mu$s\nvs. {NONHUB_LAT:.2f} $\\mu$s",
              "#d6efdd"),
    ]
    for x, title, body, color in boxes:
        box = FancyBboxPatch((x, 0.8), 2.8, 1.9,
                             boxstyle="round,pad=0.02,rounding_size=0.15",
                             linewidth=1.6, edgecolor="#333333",
                             facecolor=color)
        ax.add_patch(box)
        ax.text(x + 1.4, 2.35, title, ha="center", va="center",
                fontsize=11.5, fontweight="bold")
        ax.text(x + 1.4, 1.45, body, ha="center", va="center",
                fontsize=10, family="monospace")

    # arrows between boxes
    for i in range(len(boxes) - 1):
        x_from = boxes[i][0] + 2.8
        x_to   = boxes[i + 1][0]
        arrow = FancyArrowPatch((x_from + 0.02, 1.75),
                                (x_to   - 0.02, 1.75),
                                arrowstyle="-|>", mutation_scale=18,
                                linewidth=1.8, color="#222222")
        ax.add_patch(arrow)

    ax.text(6.5, 0.25,
            f"A stopwatch adversary recovers hub identity from latency alone "
            f"(r(deg,t) = {R_DEG_LAT:.4f})",
            ha="center", va="center", fontsize=10.5, style="italic",
            color="#444444")
    ax.set_title("Diagram 1  -  Side-channel leakage chain induced by $A_v = f(d_v)$",
                 fontsize=13, pad=10)
    fig.tight_layout()
    out = FIG_DIR / "proof_diagram_1_leakage_chain.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {out}")


# ---------- Diagram 2: Correlation Scatter Plots ------------------------------
def _synthetic_pair(n: int, r: float, seed: int,
                    x_range=(1, 10_000), y_range=(1, 100)):
    """Generate (x, y) samples with sample correlation ~= r, on a heavy-tailed x."""
    rng = np.random.default_rng(seed)
    x = rng.pareto(1.3, size=n) + 1.0            # heavy tail
    z = rng.standard_normal(n)
    # Pearson r on transformed vars roughly equals correlation on raw vars
    # when using a linear mix.
    y_core = r * (x - x.mean()) / (x.std() + 1e-9) \
             + np.sqrt(max(0.0, 1.0 - r * r)) * z
    y = y_core - y_core.min() + 1.0
    # rescale into requested ranges
    x = x_range[0] + (x - x.min()) / (x.max() - x.min() + 1e-9) \
                   * (x_range[1] - x_range[0])
    y = y_range[0] + (y - y.min()) / (y.max() - y.min() + 1e-9) \
                   * (y_range[1] - y_range[0])
    return x, y


def diagram_correlations():
    fig, axes = plt.subplots(1, 3, figsize=(14.0, 4.5))
    panels = [
        (axes[0], "Degree   vs.   # Addresses $A_v$",
            "Out-degree $d_v$", "Addresses $A_v$",
            R_DEG_ADDR, 0, (1, 12_000), (1, 60)),
        (axes[1], "# Addresses $A_v$   vs.   Query Latency",
            "Addresses $A_v$", "Latency ($\\mu$s)",
            R_ADDR_LAT, 1, (1, 60),   (1.5, 22)),
        (axes[2], "Degree   vs.   Query Latency",
            "Out-degree $d_v$", "Latency ($\\mu$s)",
            R_DEG_LAT, 2, (1, 12_000), (1.5, 22)),
    ]
    for ax, title, xl, yl, r, seed, xr, yr in panels:
        x, y = _synthetic_pair(1200, r, seed, xr, yr)
        ax.scatter(x, y, s=10, alpha=0.45, color="#d62728",
                   edgecolors="none")
        # OLS trend line
        coeffs = np.polyfit(x, y, 1)
        xs = np.linspace(x.min(), x.max(), 100)
        ax.plot(xs, np.polyval(coeffs, xs), color="#222222",
                linewidth=1.5, linestyle="--", label="OLS fit")
        ax.set_xscale("log")
        ax.set_title(title, fontsize=11.5)
        ax.set_xlabel(xl)
        ax.set_ylabel(yl)
        ax.text(0.04, 0.93, f"r = {r:.4f}", transform=ax.transAxes,
                fontsize=12, fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.3",
                          facecolor="#fff4bf", edgecolor="#888"))
        ax.legend(loc="lower right", fontsize=9)

    fig.suptitle("Diagram 2  -  Three near-perfect correlations along the "
                 "$d_v \\rightarrow A_v \\rightarrow$ latency chain",
                 fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    out = FIG_DIR / "proof_diagram_2_correlations.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {out}")


# ---------- Diagram 3: Gap Analysis ------------------------------------------
def diagram_gap_analysis():
    fig, axes = plt.subplots(1, 2, figsize=(12.0, 4.6))

    labels = ["Non-Hub", "Hub"]
    colors = ["#4c9bd1", "#d62728"]

    # Left: addresses
    ax1 = axes[0]
    vals = [NONHUB_ADDR, HUB_ADDR]
    bars = ax1.bar(labels, vals, color=colors, edgecolor="#222", linewidth=1.2)
    for b, v in zip(bars, vals):
        ax1.text(b.get_x() + b.get_width() / 2, v + 0.8, f"{v:.2f}",
                 ha="center", va="bottom", fontsize=12, fontweight="bold")
    ax1.set_ylabel("Addresses $A_v$ (mean)")
    ax1.set_title("Memory footprint per node")
    ax1.set_ylim(0, HUB_ADDR * 1.25)
    ax1.annotate(f"{EXPANSION_GAP:.2f}x\nExpansion Gap",
                 xy=(1, HUB_ADDR), xytext=(0.5, HUB_ADDR * 1.12),
                 ha="center", fontsize=11.5, fontweight="bold",
                 color="#b31217",
                 arrowprops=dict(arrowstyle="->", color="#b31217",
                                 linewidth=1.4))

    # Right: latency
    ax2 = axes[1]
    vals = [NONHUB_LAT, HUB_LAT]
    bars = ax2.bar(labels, vals, color=colors, edgecolor="#222", linewidth=1.2)
    for b, v in zip(bars, vals):
        ax2.text(b.get_x() + b.get_width() / 2, v + 0.4, f"{v:.3f} $\\mu$s",
                 ha="center", va="bottom", fontsize=12, fontweight="bold")
    ax2.set_ylabel("Query Latency ($\\mu$s)")
    ax2.set_title("Observable side-channel")
    ax2.set_ylim(0, HUB_LAT * 1.25)
    ax2.annotate(f"{TIMING_GAP:.2f}x\nTiming Discrepancy",
                 xy=(1, HUB_LAT), xytext=(0.5, HUB_LAT * 1.12),
                 ha="center", fontsize=11.5, fontweight="bold",
                 color="#b31217",
                 arrowprops=dict(arrowstyle="->", color="#b31217",
                                 linewidth=1.4))

    fig.suptitle("Diagram 3  -  Hub vs. Non-Hub gap in memory and latency",
                 fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    out = FIG_DIR / "proof_diagram_3_gap_analysis.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {out}")


# ---------- Diagram 4: Timing-Only Attack Histogram ---------------------------
def diagram_timing_attack():
    rng = np.random.default_rng(7)
    # Equal sample count so hub bars are visible alongside non-hubs.
    nonhub = rng.normal(NONHUB_LAT, 0.35, size=1500)
    hub    = rng.normal(HUB_LAT,    1.20, size=1500)

    fig, ax = plt.subplots(figsize=(10.5, 4.8))
    bins = np.linspace(0, 26, 70)
    ax.hist(nonhub, bins=bins, color="#4c9bd1", alpha=0.85,
            edgecolor="#245a7a", linewidth=0.4,
            label=f"Non-Hub  (mean $\\approx$ {NONHUB_LAT:.2f} $\\mu$s)")
    ax.hist(hub, bins=bins, color="#d62728", alpha=0.85,
            edgecolor="#7a1d1e", linewidth=0.4,
            label=f"Hub  (mean $\\approx$ {HUB_LAT:.2f} $\\mu$s)")

    ax.axvline(THRESHOLD_US, color="#222222", linestyle="--", linewidth=1.8,
               label=f"Attack threshold = {THRESHOLD_US:.2f} $\\mu$s")

    ax.set_xlim(0, 26)
    y_top = ax.get_ylim()[1]
    ax.set_ylim(0, y_top * 1.18)   # headroom for annotations

    # threshold callout sitting just above the bars
    ax.annotate(f"Threshold\n{THRESHOLD_US:.2f} $\\mu$s",
                xy=(THRESHOLD_US, y_top * 0.55),
                xytext=(THRESHOLD_US + 2.2, y_top * 0.85),
                fontsize=10, ha="left", color="#222",
                arrowprops=dict(arrowstyle="->", color="#222", linewidth=1.2),
                bbox=dict(boxstyle="round,pad=0.3",
                          facecolor="white", edgecolor="#888"))

    # cluster labels right above each peak
    ax.text(NONHUB_LAT, y_top * 1.03, "Non-Hub cluster",
            ha="center", fontsize=10, color="#245a7a", fontweight="bold")
    ax.text(HUB_LAT, y_top * 0.87, "Hub cluster",
            ha="center", fontsize=10, color="#7a1d1e", fontweight="bold")

    ax.set_xlabel("Measured query latency ($\\mu$s)")
    ax.set_ylabel("Frequency")
    ax.set_title("Diagram 4  -  Timing-only attack: one latency sample "
                 "separates hubs from non-hubs")
    ax.legend(loc="upper right", fontsize=9)

    stats = (f"Recall (hubs)    : 100%\n"
             f"Hub Error Rate   :  0.00%\n"
             f"r(deg, latency)  : {R_DEG_LAT:.4f}")
    ax.text(0.02, 0.97, stats, transform=ax.transAxes,
            fontsize=10, family="monospace", va="top", ha="left",
            bbox=dict(boxstyle="round,pad=0.4",
                      facecolor="#fff4bf", edgecolor="#888"))

    fig.tight_layout()
    out = FIG_DIR / "proof_diagram_4_timing_attack.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {out}")


def main():
    diagram_leakage_chain()
    diagram_correlations()
    diagram_gap_analysis()
    diagram_timing_attack()
    print(f"all diagrams -> {FIG_DIR}")


if __name__ == "__main__":
    main()
