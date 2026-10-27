"""Station maps, NYC vs Chicago, coloured by member share (docs/img/station_maps.png).
Run: .venv/bin/python docs/chart_station_maps.py data/marts/station_activity.csv docs/img/station_maps.png"""
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

s = pd.read_csv(sys.argv[1])
cmap = LinearSegmentedColormap.from_list("ms", ["#e8833a", "#f2f2f2", "#1f4e79"])
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11})
fig, axes = plt.subplots(1, 2, figsize=(11, 6.2), dpi=200, gridspec_kw={"wspace": 0.04})
for ax, (city, name) in zip(axes, [("NYC", "New York"), ("CHI", "Chicago")], strict=True):
    d = s[s.city_id == city].sort_values("total_trips")
    size = 600 * (d.total_trips / s[s.city_id == city].total_trips.max())
    sc = ax.scatter(d.lng, d.lat, s=size.clip(2), c=d.member_share, cmap=cmap, vmin=0.3, vmax=1.0,
                    alpha=0.85, linewidths=0)
    ax.set_title(name, fontsize=15, fontweight="bold", color="#1f4e79", loc="left")
    ax.set_aspect(1 / 0.76)
    ax.axis("off")
cb = fig.colorbar(sc, ax=axes, orientation="horizontal", fraction=0.04, pad=0.02, shrink=0.5)
cb.set_label("Member share of trips at the station (orange = mostly casual, blue = mostly members)", fontsize=11)
cb.ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
fig.savefig(sys.argv[2], bbox_inches="tight")
