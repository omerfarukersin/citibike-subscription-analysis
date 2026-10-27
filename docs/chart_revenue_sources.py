"""NYC revenue by source, Jul 2025 - Jun 2026 (docs/img/revenue_sources.png).
Run: .venv/bin/python docs/chart_revenue_sources.py data/marts/nyc_revenue_mix.csv docs/img/revenue_sources.png"""
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

mix, out = sys.argv[1], sys.argv[2]
r = pd.read_csv(mix)
y = r[r.year_month.between("2025-07", "2026-06")].groupby("category").amount_mtd_usd.sum()
y = y[y.abs() > 1].sort_values()
total = y.sum()
labels = {"Ebike Surcharges & Other Fees": "E-bike per-minute charges & other fees",
          "Casual Ridership": "Single rides & day passes (casual)", "Memberships": "Annual memberships",
          "Lyft Pink": "Lyft Pink memberships", "Sponsorship": "Sponsorship (Citi)",
          "Classic Bike Refunds & Discounts": "Refunds & discounts, classic bikes",
          "Ebike Refunds & Discounts": "Refunds & discounts, e-bikes"}
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9.5, "axes.edgecolor": "#bdbdbd",
                     "xtick.color": "#6b6b6b", "ytick.color": "#222222"})
fig, ax = plt.subplots(figsize=(8.6, 3.4), dpi=200)
colours = ["#b2182b" if v < 0 else "#2a9d8f" for v in y]
ax.barh([labels[c] for c in y.index], y / 1e6, color=colours, height=0.65)
for i, v in enumerate(y):
    share = f"{100 * v / total:.0f}%".replace("-", "\u2212") if abs(100 * v / total) >= 1 else "under 1%"
    amount = f"${v / 1e6:,.1f}M" if v >= 0 else f"\u2212${-v / 1e6:,.1f}M"
    ax.text(max(v, 0) / 1e6 + 1.5, i, f"{amount}  ({share})", va="center", ha="left", fontsize=8.5, color="#222222")
ax.set_xlim(-8, 135)
ax.set_xlabel("USD millions, Jul 2025 - Jun 2026 (before tax)", color="#6b6b6b")
ax.axvline(0, color="#bdbdbd", lw=1)
ax.grid(axis="x", color="#e6e6e6", lw=0.8)
ax.set_axisbelow(True)
for s in ("top", "right", "left"):
    ax.spines[s].set_visible(False)
ax.tick_params(axis="y", length=0)
fig.tight_layout()
fig.savefig(out)
