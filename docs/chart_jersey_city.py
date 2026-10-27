"""Jersey City scope-change charts (docs/img/jc_difference.png, jc_before_after.png). Needs the built citibike.duckdb.
Run: .venv/bin/python docs/chart_jersey_city.py citibike.duckdb docs/img"""
import sys

import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

db, out = sys.argv[1], sys.argv[2]
con = duckdb.connect(db, read_only=True)
d = con.sql("SELECT * FROM qa_report_vs_bts_jc ORDER BY year_month").df()
d["m"] = pd.to_datetime(d.year_month + "-01")
d.to_csv(f"{out}/jc_check.csv", index=False)

BLUE, ORANGE, INK, MUTED, GRID = "#2a78d6", "#eb6834", "#222222", "#6b6b6b", "#e6e6e6"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": "#bdbdbd",
                     "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED})

# Figure 1: how far each BTS count is from the report total, month by month
fig, ax = plt.subplots(figsize=(8.6, 3.9), dpi=200)
ax.axhspan(-1, 1, color="#f2f2f2", zorder=0)
ax.text(pd.Timestamp("2023-07-10"), 0.62, "within ±1% = a match", color=MUTED, fontsize=8.5, va="center")
ax.axhline(0, color="#bdbdbd", lw=1, zorder=1)
ax.axvline(pd.Timestamp("2025-03-01"), color=MUTED, lw=1, ls=(0, (4, 3)))
ax.text(pd.Timestamp("2025-03-12"), 3.15, "March 2025:\nreports start counting\nJersey City + Hoboken", color=INK,
        fontsize=8.5, va="top")
for col, colour, label in [("nyc_only_vs_report", BLUE, "BTS New York only"),
                           ("nyc_plus_jc_vs_report", ORANGE, "BTS New York + Jersey City")]:
    y = 100 * d[col]
    ax.plot(d.m, y, color=colour, lw=2, marker="o", ms=4, label=label, zorder=3)
ax.annotate("New York only matches", (pd.Timestamp("2024-06-01"), -0.1), xytext=(0, -16),
            textcoords="offset points", color=BLUE, fontsize=8.5, ha="center", fontweight="bold")
ax.annotate("New York + Jersey City matches", (pd.Timestamp("2025-11-01"), -0.5), xytext=(0, -16),
            textcoords="offset points", color=ORANGE, fontsize=8.5, ha="center", fontweight="bold")
ax.set_ylim(-3.5, 3.5)
ax.set_ylabel("Difference from report total (%)")
ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:+.0f}%" if v else "0%"))
ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 7]))
ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
ax.grid(axis="y", color=GRID, lw=0.8)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
ax.legend(loc="lower left", frameon=False, fontsize=8.5, ncol=2, bbox_to_anchor=(0, -0.02))
fig.tight_layout()
fig.savefig(f"{out}/jc_difference.png")

# Figure 2: one month before and one month after the change, as stacked bars
fig, ax = plt.subplots(figsize=(8.6, 3.3), dpi=200)
rows = d[d.year_month.isin(["2025-02", "2025-03"])].reset_index(drop=True)
labels = ["February 2025\n(before)", "March 2025\n(after)"]
for i, r in rows.iterrows():
    base = i * 3
    ax.barh(base + 1, r.report_trips / 1e6, color="#9e9e9e", height=0.7)
    ax.text(r.report_trips / 1e6 + 0.04, base + 1, f"Report total  {r.report_trips:,.0f}", va="center",
            fontsize=8.5, color=INK)
    ax.barh(base, r.bts_nyc_trips / 1e6, color=BLUE, height=0.7)
    ax.barh(base, r.bts_jc_trips / 1e6, left=r.bts_nyc_trips / 1e6 + 0.004, color=ORANGE, height=0.7)
    ax.text((r.bts_nyc_trips + r.bts_jc_trips) / 1e6 + 0.04, base,
            f"BTS: New York {r.bts_nyc_trips:,.0f} + Jersey City {r.bts_jc_trips:,.0f}", va="center",
            fontsize=8.5, color=INK)
ax.set_yticks([0.5, 3.5])
ax.set_yticklabels(labels)
ax.invert_yaxis()
ax.set_xlim(0, 4.6)
ax.set_xlabel("Trips (millions)")
for s in ("top", "right", "left"):
    ax.spines[s].set_visible(False)
ax.tick_params(axis="y", length=0)
ax.grid(axis="x", color=GRID, lw=0.8)
ax.set_axisbelow(True)
fig.tight_layout()
fig.savefig(f"{out}/jc_before_after.png")
print(d[["year_month", "nyc_only_vs_report", "nyc_plus_jc_vs_report"]].round(4).to_string(index=False))
