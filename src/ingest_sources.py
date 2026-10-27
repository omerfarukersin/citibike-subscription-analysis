"""Ingest the small sources into data/staging/:
  - BTS Docked Bikeshare Ridership, daily level, NYC + Chicago  (data.bts.gov 6cfa-ipzd)
  - NOAA GHCN-Daily weather: Central Park (NYC) and O'Hare (Chicago)
  - NYC DOT Citywide Mobility Survey 2024, Person table (data.cityofnewyork.us i2im-iqtt)
"""
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
STAGING = ROOT / "data" / "staging"
START, END = "2023-07-01", "2026-06-30"

BTS_URL = "https://data.bts.gov/resource/6cfa-ipzd.json"
BTS_SYSTEMS = {"CitiBike (New York, NY)": "NYC", "Divvy (Chicago, IL)": "CHI",
               "CitiBike (Jersey City, NJ)": "JC"}  # JC kept only to test the report's Mar 2025 scope change
NOAA_URL = "https://www.ncei.noaa.gov/data/global-historical-climatology-network-daily/access/{sid}.csv"
NOAA_STATIONS = {"NYC": "USW00094728", "CHI": "USW00094846"}  # Central Park, O'Hare
SURVEY_URL = "https://data.cityofnewyork.us/api/views/i2im-iqtt/rows.csv?accessType=DOWNLOAD"


def ingest_bts() -> None:
    rows, offset = [], 0
    systems = ",".join(f"'{s}'" for s in BTS_SYSTEMS)
    while True:
        params = {
            "$select": "sysname,yr_mo_d,membership,docked,num_trip,sum_min",
            "$where": f"sum_level=2 AND sysname in ({systems}) "
                      f"AND yr_mo_d between '{START}T00:00:00' and '{END}T00:00:00'",
            "$order": "sysname,yr_mo_d,membership,docked",
            "$limit": 50000, "$offset": offset,
        }
        batch = requests.get(BTS_URL, params=params, timeout=120).json()
        if not batch:
            break
        rows += batch
        offset += len(batch)
    df = pd.DataFrame(rows)
    (RAW / "bts").mkdir(parents=True, exist_ok=True)
    df.to_csv(RAW / "bts" / "bts_daily_raw.csv", index=False)
    df["city"] = df["sysname"].map(BTS_SYSTEMS)
    df["date"] = pd.to_datetime(df["yr_mo_d"]).dt.date
    df["rider_type"] = df["membership"].astype(float).map({1.0: "member", 0.0: "casual"})
    df["docked"] = df["docked"].astype(float).astype(int)
    for c in ("num_trip", "sum_min"):
        df[c] = df[c].astype(float)
    out = (df.groupby(["city", "date", "rider_type"], as_index=False)
             .agg(trips=("num_trip", "sum"), trip_minutes=("sum_min", "sum")))
    out[out.city == "JC"].to_csv(STAGING / "bts_daily_jersey_city.csv", index=False)
    out = out[out.city != "JC"]
    out.to_csv(STAGING / "bts_daily.csv", index=False)
    print(f"BTS: {len(df):,} raw rows -> {len(out):,} city-day-ridertype rows, "
          f"{out.date.min()} to {out.date.max()}")


def ingest_noaa() -> None:
    (RAW / "noaa").mkdir(parents=True, exist_ok=True)
    frames = []
    for city, sid in NOAA_STATIONS.items():
        path = RAW / "noaa" / f"{sid}.csv"
        if not path.exists():
            path.write_bytes(requests.get(NOAA_URL.format(sid=sid), timeout=300).content)
        d = pd.read_csv(path, usecols=["STATION", "NAME", "DATE", "PRCP", "SNOW", "SNWD", "TMAX", "TMIN", "AWND"],
                        low_memory=False)
        d = d[d["DATE"].between(START, END)].copy()
        # GHCN-Daily access files store temperature in tenths of °C, precipitation and wind in tenths
        frames.append(pd.DataFrame({
            "city": city, "station_id": d["STATION"], "station_name": d["NAME"], "date": d["DATE"],
            "tmax_c": d["TMAX"] / 10, "tmin_c": d["TMIN"] / 10, "precip_mm": d["PRCP"] / 10,
            "snow_mm": d["SNOW"], "snow_depth_mm": d["SNWD"], "wind_ms": d["AWND"] / 10,
        }))
    out = pd.concat(frames)
    out.to_csv(STAGING / "weather_daily.csv", index=False)
    print(f"NOAA: {len(out):,} station-days; missing tmax={out.tmax_c.isna().sum()}, "
          f"missing precip={out.precip_mm.isna().sum()}")


def ingest_survey() -> None:
    path = RAW / "survey" / "cms_2024_person.csv"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(requests.get(SURVEY_URL, timeout=300).content)
    p = pd.read_csv(path, low_memory=False)
    keep = ["hh_id", "person_id", "age", "gender", "employment", "citi_bike_freq", "citi_bike_type",
            "citi_bike_pay"] + [f"no_bike_share_{i}" for i in range(1, 9)] + ["person_weight_citywide"]
    p = p[keep].copy()
    p.to_csv(STAGING / "survey_person_2024.csv", index=False)
    print(f"Survey: {len(p):,} persons; Citi Bike plan answered by "
          f"{(~p.citi_bike_pay.isin([995])).sum():,}")


if __name__ == "__main__":
    STAGING.mkdir(parents=True, exist_ok=True)
    ingest_bts()
    ingest_noaa()
    ingest_survey()
