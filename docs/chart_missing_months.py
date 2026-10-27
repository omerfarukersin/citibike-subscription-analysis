"""Monthly revenue chart, reported vs derived-from-YTD months (docs/img/revenue_monthly.png).

Needs data/staging (run `make extract`).
Run: .venv/bin/python docs/chart_missing_months.py data/staging/nyc_revenue.csv docs/img/revenue_monthly.png"""
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

staging, out = sys.argv[1], sys.argv[2]
t = pd.read_csv(staging)
t = t[t.category == "TOTAL"].sort_values("month")
BLUE, ORANGE, MUTED, GRID = "#2a78d6", "#eb6834", "#6b6b6b", "#e6e6e6"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9.5, "axes.edgecolor": "#bdbdbd",
                     "xtick.color": MUTED, "ytick.color": MUTED, "axes.labelcolor": MUTED})
fig, ax = plt.subplots(figsize=(8.6, 3.6), dpi=200)
x = range(len(t))
colours = [ORANGE if b == "derived_from_ytd" else BLUE for b in t.basis]
ax.bar(x, t.amount_mtd_usd / 1e6, color=colours, width=0.72)
for i, (m, v, b) in enumerate(zip(t.month, t.amount_mtd_usd, t.basis, strict=True)):
    if b == "derived_from_ytd":
        ax.annotate(f"{pd.Timestamp(m + '-01'):%b %Y}\n${v / 1e6:.1f}M", xy=(i, v / 1e6),
                    xytext=(i, 16 if m.endswith("-02") else 35.5),
                    ha="center", va="bottom", fontsize=8.5, color=ORANGE, fontweight="bold",
                    arrowprops=dict(arrowstyle="-", color=ORANGE, lw=0.8))
ticks = [i for i, m in enumerate(t.month) if m.endswith(("-01", "-07"))]
ax.set_xticks(ticks, [f"{pd.Timestamp(t.month.iloc[i] + '-01'):%b %Y}" for i in ticks])
ax.set_ylabel("Total revenue (USD millions)")
ax.set_ylim(0, 40)
ax.grid(axis="y", color=GRID, lw=0.8)
ax.set_axisbelow(True)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
ax.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=BLUE), plt.Rectangle((0, 0), 1, 1, color=ORANGE)],
          labels=["Reported in the monthly report", "Calculated from year-to-date totals"],
          loc="upper left", frameon=False, fontsize=8.5)
fig.tight_layout()
fig.savefig(out)
