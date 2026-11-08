#!/usr/bin/env python3
"""Figures for the two workshop papers. Every number is copied from the
run outputs; nothing is recomputed here."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2, GRID = "#0b0b0b", "#52514e", "#d9d8d4"

plt.rcParams.update({
    "font.family": "serif", "font.serif": ["Liberation Serif"],
    "font.size": 8, "axes.titlesize": 8, "axes.labelsize": 8,
    "xtick.labelsize": 7.5, "ytick.labelsize": 7.5, "legend.fontsize": 7.5,
    "axes.edgecolor": INK2, "axes.linewidth": 0.6, "xtick.color": INK2,
    "ytick.color": INK2, "axes.labelcolor": INK, "pdf.fonttype": 42,
    "axes.spines.top": False, "axes.spines.right": False,
})
W = 3.3  # AAAI column width, inches


def grid(ax, axis="y"):
    ax.grid(axis=axis, color=GRID, linewidth=0.5)
    ax.set_axisbelow(True)


# ---------------------------------------------------------------- W3PHIAI
def w3_coverage(out):
    corpora = ["Wikipedia", "PubMed\nabstracts", "Both\ntogether"]
    ind = [20.33, 26.31, 29.04]
    con = [9.81, 11.44, 15.91]
    orr = ["OR 2.43", "OR 2.77", "OR 2.19"]
    fig, ax = plt.subplots(figsize=(W, 1.9))
    x = range(len(corpora))
    bw = 0.36
    b1 = ax.bar([i - bw / 2 - 0.01 for i in x], ind, bw, color=BLUE,
                label="Indication")
    b2 = ax.bar([i + bw / 2 + 0.01 for i in x], con, bw, color=ORANGE,
                hatch="////", edgecolor="white", linewidth=0,
                label="Contraindication")
    for i in x:
        ax.text(i - bw / 2 - 0.01, ind[i] + 0.6, f"{ind[i]:.1f}", ha="center",
                va="bottom", fontsize=7, color=INK)
        ax.text(i + bw / 2 + 0.01, con[i] + 0.6, f"{con[i]:.1f}", ha="center",
                va="bottom", fontsize=7, color=INK)
        ax.text(i, max(ind[i], con[i]) + 4.2, orr[i], ha="center",
                fontsize=7, color=INK2, style="italic")
    ax.set_xticks(list(x))
    ax.set_xticklabels(corpora)
    ax.set_ylabel("Facts named in text (%)")
    ax.set_ylim(0, 35)
    grid(ax)
    ax.legend(loc="lower center", frameon=False, ncol=2, handlelength=1.2,
              bbox_to_anchor=(0.5, 1.0))
    fig.tight_layout(pad=0.3)
    fig.savefig(out)


def w3_scale(out):
    rels = [("Indication", 31.50, 50.83, (27.91, 35.32), (46.84, 54.82), BLUE, "o"),
            ("Off-label use", 28.50, 35.00, (25.03, 32.24), (31.29, 38.90), AQUA, "s"),
            ("Contraindication", 22.17, 23.83, (19.03, 25.66), (20.60, 27.40), ORANGE, "D")]
    fig, ax = plt.subplots(figsize=(W, 2.0))
    xs = [0, 1]
    for name, a, b, ca, cb, col, m in rels:
        ax.plot(xs, [a, b], color=col, linewidth=2, marker=m, markersize=5,
                markeredgecolor="white", markeredgewidth=0.8, zorder=3)
        for xx, v, ci in ((0, a, ca), (1, b, cb)):
            ax.plot([xx, xx], ci, color=col, linewidth=1, alpha=0.6, zorder=2)
        gain = {"Indication": 19.33, "Off-label use": 6.50,
                "Contraindication": 1.67}[name]
        ax.text(1.06, b, f"{name}  +{gain:.1f}", va="center", fontsize=7.5,
                color=INK)
    ax.axhline(20, color=INK2, linewidth=0.8, linestyle=(0, (3, 2)))
    ax.text(0.5, 18.3, "chance (20%)", ha="center", fontsize=7, color=INK2)
    ax.set_xticks(xs)
    ax.set_xticklabels(["Qwen2.5 0.5B", "Qwen2.5 7B"])
    ax.set_xlim(-0.15, 1.95)
    ax.set_ylim(15, 56)
    ax.set_ylabel("Accuracy, closed book (%)")
    ax.spines["bottom"].set_bounds(0, 1)
    grid(ax)
    fig.tight_layout(pad=0.3)
    fig.savefig(out)


def w3_degree(out):
    strata = ["3–5", "6–12", "13+"]
    wiki = [13.94, 6.04, 1.64]
    both = [11.81, 6.90, 2.23]
    fig, ax = plt.subplots(figsize=(W, 1.7))
    x = range(3)
    ax.plot(x, wiki, color=BLUE, marker="o", linewidth=2, markersize=5,
            markeredgecolor="white", label="Wikipedia")
    ax.plot(x, both, color=AQUA, marker="s", linewidth=2, markersize=5,
            markeredgecolor="white", label="Wikipedia + PubMed")
    ax.axhline(0, color=INK2, linewidth=0.6)
    ax.set_xticks(list(x))
    ax.set_xticklabels(strata)
    ax.set_xlabel("Edges per drug in the relation")
    ax.set_ylabel("Indication minus\ncontraindication (pts)")
    ax.set_ylim(-1, 17)
    grid(ax)
    ax.legend(frameon=False, loc="upper right")
    fig.tight_layout(pad=0.3)
    fig.savefig(out)


# ------------------------------------------------------------- NeusymBridge
def ns_forest(out):
    models = ["Qwen2.5 0.5B", "Qwen2.5 7B", "OLMo 2 7B", "Granite 3.1 8B",
              "Qwen2.5 14B", "Pooled, 7–8B"]
    data = {
        "Declines": [(-8.4, -15.7, -1.1), (-1.1, -10.5, 8.4), (-22.1, -31.8, -12.6),
                     (-18.2, -28.5, -8.1), (5.3, -4.6, 15.1), (-13.8, -20.3, -7.5)],
        "Correct": [(4.2, -6.1, 14.4), (2.4, -5.7, 10.5), (7.3, -2.6, 17.0),
                    (8.5, -0.9, 17.8), (0.1, -7.7, 8.0), (6.1, -0.1, 12.4)],
        "Wrong": [(4.2, -6.4, 14.6), (-1.3, -9.4, 7.1), (14.8, 3.6, 26.1),
                  (9.7, -0.1, 19.9), (-5.4, -13.1, 2.4), (7.7, 1.2, 14.0)],
    }
    fig, axes = plt.subplots(1, 3, figsize=(2 * W + 0.33, 1.95), sharey=True)
    ys = [5.6, 4.6, 3.6, 2.6, 1.6, 0.0]
    for ax, (name, rows) in zip(axes, data.items()):
        for y, (m, lo, hi), mod in zip(ys, rows, models):
            pooled = mod.startswith("Pooled")
            small = mod.endswith("0.5B") or mod.endswith("14B")
            col = INK2 if small else (INK if pooled else BLUE)
            ax.plot([lo, hi], [y, y], color=col, linewidth=1.2)
            ax.plot(m, y, marker="D" if pooled else "o",
                    markersize=6 if pooled else 4.5, color=col,
                    markeredgecolor="white", markeredgewidth=0.6, zorder=3)
        ax.axvline(0, color=INK2, linewidth=0.7, linestyle=(0, (3, 2)))
        ax.axhline(0.8, color=GRID, linewidth=0.6)
        ax.set_title(name, fontsize=8.5, color=INK)
        ax.set_xlim(-34, 28)
        ax.set_xticks([-30, -20, -10, 0, 10, 20])
        ax.grid(axis="x", color=GRID, linewidth=0.5)
        ax.set_axisbelow(True)
        ax.tick_params(axis="y", length=0)
        ax.spines["left"].set_visible(False)
    axes[0].set_yticks(ys)
    axes[0].set_yticklabels(models)
    axes[1].set_xlabel("Page effect on family-only questions minus page effect "
                       "on silent questions (percentage points, 95% CI)")
    fig.tight_layout(pad=0.3, w_pad=0.8)
    fig.savefig(out)


def ns_fixes(out):
    fig, axes = plt.subplots(1, 3, figsize=(2 * W + 0.33, 1.85),
                             gridspec_kw={"width_ratios": [1.15, 1.2, 0.95]})
    # (a) AUROC by page type
    ax = axes[0]
    models = ["Qwen2.5 0.5B", "Qwen2.5 7B", "OLMo 2 7B", "Granite 3.1 8B", "Qwen2.5 14B"]
    named = [0.85, 0.73, 0.86, 0.87, 0.77]
    fam = [0.64, 0.72, 0.71, 0.66, 0.59]
    sil = [0.70, 0.77, 0.65, 0.76, 0.68]
    ys = list(range(len(models)))[::-1]
    for y, a, b in zip(ys, named, fam):
        ax.plot([b, a], [y, y], color=GRID, linewidth=2.2, zorder=1)
    ax.scatter(named, ys, color=AQUA, s=22, zorder=3, label="named", edgecolor="white", linewidth=0.5)
    ax.scatter(fam, ys, color="#d9a321", s=22, zorder=3, label="family only", edgecolor="white", linewidth=0.5)
    ax.scatter(sil, ys, color=INK2, s=14, marker="s", zorder=2, label="silent")
    ax.set_yticks(ys); ax.set_yticklabels(models)
    ax.set_xlim(0.36, 0.92); ax.set_xticks([0.4, 0.5, 0.6, 0.7, 0.8, 0.9]); ax.set_xlabel("AUROC of confidence")
    ax.set_title("(a) Confidence", fontsize=8.5)
    ax.legend(frameon=False, fontsize=6.5, loc="lower left", handletextpad=0.2, borderpad=0.1)
    grid(ax, "x"); ax.tick_params(axis="y", length=0); ax.spines["left"].set_visible(False)
    # (b) instruction effect
    ax = axes[1]
    pages = ["named", "family", "silent"]
    vals = {"Declines": [(9.1, 6.0, 12.6), (15.2, 12.4, 18.1), (14.0, 10.6, 17.1)],
            "Correct": [(-6.3, -9.4, -3.5), (-6.2, -8.2, -4.2), (-8.1, -10.8, -5.6)],
            "Wrong": [(-2.8, -5.0, -0.9), (-9.0, -11.8, -6.2), (-5.8, -8.3, -3.5)]}
    cols = {"Declines": INK2, "Correct": AQUA, "Wrong": ORANGE}
    bw = 0.26
    for k, (nm, rows) in enumerate(vals.items()):
        xs = [i + (k - 1) * bw for i in range(3)]
        ax.bar(xs, [r[0] for r in rows], bw * 0.92, color=cols[nm], label=nm)
        ax.errorbar(xs, [r[0] for r in rows], yerr=[[r[0] - r[1] for r in rows], [r[2] - r[0] for r in rows]],
                    fmt="none", ecolor=INK, elinewidth=0.6, capsize=1.5)
    ax.axhline(0, color=INK2, linewidth=0.6)
    ax.set_xticks(range(3)); ax.set_xticklabels(["named page", "family-only", "silent page"])
    ax.set_ylabel("change (points)")
    ax.set_title("(b) Instruction to decline", fontsize=8.5)
    ax.legend(frameon=False, fontsize=6.5, ncol=3, loc="upper center", bbox_to_anchor=(0.5, 1.0),
              handlelength=0.9, columnspacing=0.6)
    ax.set_ylim(-14, 24); grid(ax)
    # (c) family size
    ax = axes[2]
    lab = ["≤10\n(med. 7)", "11–20\n(med. 16)", ">20\n(med. 44)"]
    eff = [(-17.3, -26.2, -8.2), (-18.4, -26.6, -10.3), (-6.5, -15.7, 3.0)]
    for i, (m, lo, hi) in enumerate(eff):
        ax.plot([i, i], [lo, hi], color=BLUE, linewidth=1.3)
        ax.plot(i, m, "o", color=BLUE, markersize=5, markeredgecolor="white", markeredgewidth=0.6)
    ax.axhline(0, color=INK2, linewidth=0.7, linestyle=(0, (3, 2)))
    ax.set_xticks(range(3)); ax.set_xticklabels(lab, fontsize=7)
    ax.set_xlim(-0.5, 2.5); ax.set_ylabel("decline effect (points)")
    ax.set_xlabel("family members")
    ax.set_title("(c) Size of the family", fontsize=8.5)
    grid(ax)
    fig.tight_layout(pad=0.3, w_pad=0.9)
    fig.savefig(out)


def ns_recovery(out):
    rows = [
        ("Most-studied disease (ignores drug)", 46.8, INK2, ""),
        ("PubMed co-mention with the drug", 35.9, BLUE, ""),
        ("Model picks from the list", 35.9, BLUE, ""),
        ("PubMed, normalized by popularity", 25.4, BLUE, ""),
        ("Wikipedia page names the drug", 10.0, BLUE, ""),
        ("Page in prompt + random candidates", 32.7, ORANGE, ""),
        ("End to end, family read from page", 10.0, ORANGE, ""),
    ]
    fig, ax = plt.subplots(figsize=(W, 2.15))
    for i, (name, v, col, note) in enumerate(rows):
        y = len(rows) - 1 - i
        ax.barh(y, v, height=0.62, color=col,
                hatch="////" if col == ORANGE else None, edgecolor="white",
                linewidth=0)
        ax.text(v + 0.8, y, f"{v:.1f}" + (f"  ({note})" if note else ""),
                va="center", fontsize=7, color=INK)
    ax.axhline(1.5, color=INK2, linewidth=0.6, linestyle=(0, (3, 2)))
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r[0] for r in rows][::-1])
    ax.set_xlim(0, 60)
    ax.set_xlabel("Any true disease picked (% of 410 facts)")
    ax.text(59, 5.0, "family\ngiven", ha="right", fontsize=7, color=INK2,
            style="italic", va="center")
    ax.text(59, 0.5, "family not\ngiven", ha="right", fontsize=7,
            color=INK2, style="italic", va="center")
    grid(ax, "x")
    ax.tick_params(axis="y", length=0)
    fig.tight_layout(pad=0.3)
    fig.savefig(out)


def ns_concept(out):
    fig, ax = plt.subplots(figsize=(2 * W + 0.33, 1.45))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 22)
    ax.axis("off")

    def box(x, y, w, h, text, fc="#f3f2ee", ec=INK2, bold=False, fs=7.5):
        ax.add_patch(FancyBboxPatch((x, y), w, h,
                                    boxstyle="round,pad=0.25,rounding_size=0.8",
                                    fc=fc, ec=ec, lw=0.7))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
                fontsize=fs, color=INK, weight="bold" if bold else "normal",
                wrap=True)

    def arrow(x1, y1, x2, y2, col=INK2):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="-|>", color=col, lw=0.8,
                                    shrinkA=0, shrinkB=0))

    box(0.5, 13, 21, 7.5, "Question\nWhat does lovastatin treat?\n"
        "Answer: familial hyperlipidemia", fs=7)
    box(0.5, 1.5, 21, 8.5, "Page names only the family\n“lovastatin is used\n"
        "to treat hyperlipidemia”", fc="#fdeee6", ec=ORANGE, fs=7)
    arrow(22, 6, 30, 6)
    box(30.5, 1.5, 22, 19, "", fc="white")
    ax.text(41.5, 18.2, "What a model can do", ha="center", fontsize=7.5,
            weight="bold", color=INK)
    ax.text(41.5, 13.6, "Answer anyway", ha="center", fontsize=7.2,
            color=INK)
    ax.text(41.5, 11.2, "13.8 pts fewer declines than a silent page", ha="center",
            fontsize=6.6, color=INK2)
    ax.text(41.5, 7.6, "Decline", ha="center", fontsize=7.2, color=INK)
    ax.text(41.5, 5.2, "what a silent page triggers", ha="center", fontsize=6.6,
            color=INK2)
    ax.text(41.5, 2.6, "Look further  →", ha="center", fontsize=7.2,
            color=BLUE, weight="bold")
    arrow(53, 3, 60, 3, BLUE)
    box(60.5, 1.5, 18, 19, "", fc="#e9f1fb", ec=BLUE)
    ax.text(69.5, 18.2, "Members of the family", ha="center", fontsize=7.5,
            weight="bold", color=INK)
    for k, t in enumerate(["familial hyperlipidemia",
                           "hyperlipidemia, familial\ncombined, LPL related",
                           "\u2026 8 candidates in all"]):
        ax.text(69.5, [14.6, 9.9, 5.0][k], t, ha="center", va="center",
                fontsize=6.8, color=INK, linespacing=1.1)
    arrow(79, 11, 86, 11, BLUE)
    box(86.5, 6, 13, 10, "Pick a member\nfrom evidence\nor a prior", fc="white",
        ec=BLUE, fs=7)
    fig.tight_layout(pad=0.2)
    fig.savefig(out)


if __name__ == "__main__":
    # figures 1 and 3 (fig_concept, fig_edit) are draw.io files in drawio/
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    ns_forest(os.path.join(here, "fig_forest.pdf"))
    ns_recovery(os.path.join(here, "fig_recovery.pdf"))
    ns_fixes(os.path.join(here, "fig_fixes.pdf"))
    print("ok")
