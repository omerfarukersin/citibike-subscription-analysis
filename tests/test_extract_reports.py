import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from extract_reports import check_ytd, derive_missing, money  # noqa: E402


@pytest.mark.parametrize("raw, expected", [
    ("$ 3,453.76", 3453.76), ("$ (348.90)", -348.90), ("-$222.09", -222.09), ("$-191.25", -191.25), ("-", None),
])
def test_money(raw, expected):
    assert money(raw) == expected


def _rev(month, cat, mtd, ytd):
    return {"month": month, "category": cat, "amount_mtd_usd": mtd, "amount_ytd_usd": ytd,
            "basis": "reported", "found": True, "source_file": f"{month}.pdf"}


def test_derive_missing_month_from_ytd():
    # Jan 100, Feb unpublished (true value 250), Mar 400 -> YTD end Mar = 750
    rev = pd.DataFrame([_rev("2026-01", "Memberships", 100.0, 100.0),
                        _rev("2026-03", "Memberships", 400.0, 750.0)])
    out = derive_missing(rev, ["2026-02"])
    assert out.loc[0, "amount_mtd_usd"] == 250.0
    assert out.loc[0, "amount_ytd_usd"] == 350.0
    assert out.loc[0, "basis"] == "derived_from_ytd"


def test_derive_missing_january_uses_zero_start():
    rev = pd.DataFrame([_rev("2026-02", "Memberships", 80.0, 200.0)])
    out = derive_missing(rev, ["2026-01"])
    assert out.loc[0, "amount_mtd_usd"] == 120.0


def test_no_derivation_without_both_neighbours():
    rev = pd.DataFrame([_rev("2026-01", "Memberships", 100.0, 100.0)])
    assert derive_missing(rev, ["2026-02"]).empty


def test_check_ytd_treats_dash_mtd_as_zero():
    # a month whose MTD is reported as '-' (NaN) must still be a real check, not a row of NaN
    rev = pd.DataFrame([_rev("2026-01", "Overages", 50.0, 50.0),
                        _rev("2026-02", "Overages", float("nan"), 50.0),
                        _rev("2026-03", "Overages", 10.0, 70.0)])
    out = check_ytd(rev).set_index("month")
    assert not out.isna().any().any()
    assert out.loc["2026-02", "difference"] == 0.0
    assert out.loc["2026-03", "difference"] == 10.0  # YTD 70 - MTD 10 = 60 vs previous YTD 50: a later revision


def test_check_ytd_skips_month_after_unpublished_report():
    rev = pd.DataFrame([_rev("2026-01", "Memberships", 100.0, 100.0),
                        _rev("2026-03", "Memberships", 400.0, 750.0)])
    assert list(check_ytd(rev).month) == ["2026-01"]
