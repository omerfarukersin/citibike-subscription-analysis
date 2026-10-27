"""Download trip files and convert each to Parquet with only the columns used, then delete the zip.
  - a seasonal sample (one month per season: Jul 2025, Oct 2025, Jan 2026, Apr 2026) for NYC and Chicago
  - all 36 Chicago months (Jul 2023 - Jun 2026), used for Chicago daily ridership

Sources:
  NYC Citi Bike  https://s3.amazonaws.com/tripdata/index.html
  Chicago Divvy  https://divvy-tripdata.s3.amazonaws.com/index.html
"""
import shutil
import zipfile
from pathlib import Path

import duckdb
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "trips"
STAGING = ROOT / "data" / "staging" / "trips"
SAMPLE_MONTHS = ["202507", "202510", "202601", "202604"]
CHI_ALL_MONTHS = [p.strftime("%Y%m") for p in pd.period_range("2023-07", "2026-06", freq="M")]
SOURCES = {
    "NYC": "https://s3.amazonaws.com/tripdata/{ym}-citibike-tripdata.zip",
    "CHI": "https://divvy-tripdata.s3.amazonaws.com/{ym}-divvy-tripdata.zip",
}
COLUMNS = """ride_id, rideable_type, started_at::TIMESTAMP AS started_at, ended_at::TIMESTAMP AS ended_at,
start_station_id::VARCHAR AS start_station_id, start_station_name,
end_station_id::VARCHAR AS end_station_id, end_station_name,
start_lat::DOUBLE AS start_lat, start_lng::DOUBLE AS start_lng,
end_lat::DOUBLE AS end_lat, end_lng::DOUBLE AS end_lng, member_casual"""


def download(url: str, dest: Path) -> None:
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    STAGING.mkdir(parents=True, exist_ok=True)
    jobs = [(ym, city) for ym in SAMPLE_MONTHS for city in SOURCES]
    # Chicago: all 36 months (small files). BTS double-counts Divvy in Jan 2026, so Chicago daily ridership
    # is built from Divvy's own trip files; BTS is kept as a cross-check.
    jobs += [(ym, "CHI") for ym in CHI_ALL_MONTHS if (ym, "CHI") not in jobs]
    for ym, city in jobs:
        out = STAGING / f"{city}_{ym}.parquet"
        if out.exists():
            print(f"skip {out.name}", flush=True)
            continue
        url = SOURCES[city].format(ym=ym)
        zpath = RAW / f"{city}_{ym}.zip"
        print(f"download {url}", flush=True)
        download(url, zpath)
        xdir = RAW / f"{city}_{ym}"
        with zipfile.ZipFile(zpath) as z:
            members = [m for m in z.namelist() if m.endswith(".csv") and "__MACOSX" not in m]
            z.extractall(xdir, members)
        csvs = [str(p) for p in xdir.rglob("*.csv")]
        con = duckdb.connect()
        con.execute(
            f"COPY (SELECT '{city}' AS city, {COLUMNS} FROM read_csv({csvs}, union_by_name=true, all_varchar=true)) "
            f"TO '{out}' (FORMAT parquet)"
        )
        n = con.execute(f"SELECT count(*) FROM '{out}'").fetchone()[0]
        con.close()
        print(f"wrote {out.name}: {n:,} rows from {len(csvs)} csv(s)", flush=True)
        # keep the source file list for provenance, then free disk space
        (STAGING / f"{city}_{ym}.source.txt").write_text(f"{url}\n" + "\n".join(Path(c).name for c in csvs))
        shutil.rmtree(xdir)
        zpath.unlink()
    print("done", flush=True)


if __name__ == "__main__":
    main()
