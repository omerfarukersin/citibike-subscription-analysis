"""Chart: trips on rain days vs dry days, by city and rider type (Figure 2 of docs/project_report.pdf).

Reads data/marts/weather_rain_effect.csv. Each value is the average normal-day ratio in a rain band divided by the
same ratio on dry days, minus 1 (the comparison used in the README H1 row and docs/findings.md).
Run from the repo root:  .venv/bin/python docs/chart_rain_effect.py
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "img" / "rain_vs_dry.png"

MEMBER, CASUAL = "#2A6FBB", "#E07B2E"
INK, MUTED, GRID = "#1F2328", "#59636E", "#E6E8EB"
BANDS = ["2 Light (<5 mm)", "3 Moderate (5-20 mm)", "4 Heavy (20+ mm)"]
LABELS = ["Light\n(<5 mm)", "Moderate\n(5-20 mm)", "Heavy\n(20+ mm)"]

df = pd.read_csv(ROOT / "data" / "marts" / "weather_rain_effect.csv")
dry = df[df.rain_band == "1 Dry"].set_index(["city_id", "rider_type"]).avg_trips_vs_baseline
df["vs_dry"] = df.apply(lambda r: r.avg_trips_vs_baseline / dry[(r.city_id, r.rider_type)] - 1, axis=1)

plt.rcParams.update({"font.family": "Arial", "font.size": 10})
fig, axes = plt.subplots(1, 2, figsize=(8.2, 3.6), sharey=True)
width = 0.36
for ax, (city, title) in zip(axes, [("NYC", "New York"), ("CHI", "Chicago")], strict=True):
    for i, (rider, color, label) in enumerate([("member", MEMBER, "Members"), ("casual", CASUAL, "Casual riders")]):
        vals = [df[(df.city_id == city) & (df.rider_type == rider) & (df.rain_band == b)].vs_dry.iloc[0] for b in BANDS]
        xs = [x + (i - 0.5) * (width + 0.03) for x in range(len(BANDS))]
        ax.bar(xs, [v * 100 for v in vals], width=width, color=color, label=label, zorder=3)
        for x, v in zip(xs, vals, strict=True):
            ax.text(x, v * 100 - 1.5, f"{round(v * 100):d}%", ha="center", va="top", fontsize=9, color=INK)
    ax.set_title(title, loc="left", fontsize=11, color=INK, fontweight="bold")
    ax.set_xticks(range(len(BANDS)), LABELS, color=MUTED)
    ax.axhline(0, color=MUTED, lw=0.8, zorder=4)
    ax.set_ylim(-52, 2)
    ax.grid(axis="y", color=GRID, lw=0.8, zorder=0)
    ax.tick_params(axis="both", length=0, colors=MUTED)
    for s in ax.spines.values():
        s.set_visible(False)
axes[0].set_ylabel("Trips vs a dry day (%)", color=MUTED)
axes[0].yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:.0f}%"))
handles, labels = axes[0].get_legend_handles_labels()
fig.legend(handles, labels, loc="upper right", ncol=2, frameon=False, fontsize=9.5)
fig.text(0.01, 0.01, "Both sides measured on the normal-day ratio (same city, rider type, month, weekday/weekend). "
         "Jul 2023 - Jun 2026, holidays excluded.", fontsize=7.5, color=MUTED)
fig.tight_layout(rect=(0, 0.04, 1, 0.94))
fig.savefig(OUT, dpi=200, facecolor="white")
print(OUT)
