import sys, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
INK, INK2, GRID = "#0b0b0b", "#52514e", "#d9d8d4"
COL = {"Declines": "#2a78d6", "Wrong": "#eb6834", "Correct": "#1baf7a"}
plt.rcParams.update({
    "font.family": "serif", "font.serif": ["Liberation Serif"],
    "font.size": 7.5, "xtick.labelsize": 7, "ytick.labelsize": 7.5,
    "legend.fontsize": 7, "axes.edgecolor": INK2, "axes.linewidth": 0.6,
    "xtick.color": INK2, "ytick.color": INK, "pdf.fonttype": 42,
    "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False})
# copied from build_figures.py (run outputs)
models = ["Qwen2.5 0.5B", "Qwen2.5 7B", "OLMo 2 7B", "Granite 3.1 8B",
          "Qwen2.5 14B", "Pooled 7–8B"]
data = {
 "Declines": [(-8.4,-15.7,-1.1),(-1.1,-10.5,8.4),(-22.1,-31.8,-12.6),(-18.2,-28.5,-8.1),(5.3,-4.6,15.1),(-13.8,-20.3,-7.5)],
 "Wrong":    [(4.2,-6.4,14.6),(-1.3,-9.4,7.1),(14.8,3.6,26.1),(9.7,-0.1,19.9),(-5.4,-13.1,2.4),(7.7,1.2,14.0)],
 "Correct":  [(4.2,-6.1,14.4),(2.4,-5.7,10.5),(7.3,-2.6,17.0),(8.5,-0.9,17.8),(0.1,-7.7,8.0),(6.1,-0.1,12.4)],
}
ys = [6.0, 5.0, 4.0, 3.0, 2.0, 0.55]
off = {"Declines": 0.26, "Wrong": 0.0, "Correct": -0.26}
fig, ax = plt.subplots(figsize=(3.3, 2.15))
ax.axhspan(-0.05, 1.15, color="#f3f2ee", zorder=0, lw=0)
for name, rows in data.items():
    for y, (m, lo, hi), mod in zip(ys, rows, models):
        pooled = mod.startswith("Pooled")
        faint = mod.endswith("0.5B") or mod.endswith("14B")
        yy = y + off[name]
        a = 0.45 if faint else 1.0
        ax.plot([lo, hi], [yy, yy], color=COL[name], lw=1.5 if pooled else 1.1, alpha=a, solid_capstyle="round")
        ax.plot(m, yy, marker="D" if pooled else "o", ms=5 if pooled else 3.8, color=COL[name],
                mec="white", mew=0.5, alpha=a, zorder=3)
ax.axvline(0, color=INK2, lw=0.7, ls=(0, (3, 2)))
ax.set_yticks(ys); ax.set_yticklabels(models)
for t, mod in zip(ax.get_yticklabels(), models):
    if mod.startswith("Pooled"): t.set_fontweight("bold")
    if mod.endswith("0.5B") or mod.endswith("14B"): t.set_color(INK2)
ax.tick_params(axis="y", length=0)
ax.set_xlim(-34, 28); ax.set_xticks([-30, -20, -10, 0, 10, 20])
ax.set_ylim(-0.15, 6.5)
ax.grid(axis="x", color=GRID, lw=0.5); ax.set_axisbelow(True)
ax.set_xlabel(r"$\Delta$: family-only minus silent page effect (points, 95% CI)", fontsize=7.2)
ax.text(-33, 6.47, "fewer", fontsize=6.5, color=INK2, va="top")
ax.text(27, 6.47, "more", fontsize=6.5, color=INK2, va="top", ha="right")
h = [Line2D([0], [0], color=COL[k], marker="o", ms=4, lw=1.1, label=k) for k in data]
ax.legend(handles=h, loc="upper center", bbox_to_anchor=(0.5, 1.13), ncol=3, frameon=False,
          handlelength=1.4, columnspacing=1.2, borderaxespad=0)
fig.tight_layout(pad=0.25)
fig.savefig(sys.argv[1])
fig.savefig(sys.argv[1].replace(".pdf", ".png"), dpi=300)
