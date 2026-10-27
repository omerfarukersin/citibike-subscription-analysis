"""Assertions on the committed QA and mart outputs (no database needed)."""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def test_revenue_ytd_checks_are_complete():
    checks = pd.read_csv(ROOT / "qa" / "revenue_ytd_checks.csv")
    assert not checks.isna().any().any()
    assert (checks.ytd_minus_mtd - checks.previous_ytd - checks.difference).abs().max() < 0.02


def test_report_vs_bts_nyc_before_scope_change():
    # BTS NYC and the Citi Bike report agree within 1% until the reports add Jersey City/Hoboken (Mar 2025)
    q = pd.read_csv(ROOT / "qa" / "qa_report_vs_bts.csv")
    assert q.loc[q.year_month < "2025-03", "bts_vs_report_diff"].abs().max() < 0.01


def test_trip_sample_matches_bts():
    # Jan 2026 Chicago is excluded: BTS double-counts Divvy that month (see qa_chi_files_vs_bts.csv)
    q = pd.read_csv(ROOT / "qa" / "qa_sample_vs_bts.csv")
    q = q[~((q.city_id == "CHI") & (q.year_month == "2026-01"))]
    assert q.sample_vs_bts_diff.abs().max() < 0.001


def test_monthly_kpis_columns():
    cols = pd.read_csv(ROOT / "data" / "marts" / "nyc_monthly_kpis.csv", nrows=0).columns
    assert {"rider_revenue", "rider_revenue_per_trip"} <= set(cols)
