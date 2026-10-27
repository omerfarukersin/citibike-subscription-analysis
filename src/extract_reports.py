"""Extract figures from the Citi Bike monthly operating reports (PDF) with regular expressions.

Every value comes from the report text; anything not found stays NULL and is listed in
qa/report_extraction_issues.csv. Outputs (data/staging/):
  nyc_monthly_operations.csv   one row per month (membership, trips, support, stations, fleet)
  nyc_pass_sales.csv           month x pass type x quantity
  nyc_revenue.csv              month x revenue category x amount (month-to-date)
Revenue for unpublished months is calculated from the year-to-date columns of the neighbouring reports
(basis = 'derived_from_ytd'); every month's YTD columns are cross-checked in qa/revenue_ytd_checks.csv.
"""
import re
from pathlib import Path

import pandas as pd
import pypdf

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "data" / "raw" / "reports"
STAGING = ROOT / "data" / "staging"
NUM = r"([\d,]+(?:\.\d+)?)"


def to_num(s):
    return float(s.replace(",", "")) if s is not None else None


def money(s):
    """Parse '$ 3,453.76', '$ (348.90)', '-$222.09', '$-191.25'; '-' (reported as a dash) -> None."""
    s = s.strip()
    if s == "-":
        return None
    neg = "(" in s or s.startswith("-") or "$-" in s
    v = float(re.sub(r"[^\d.]", "", s))
    return -v if neg else v


def nz(x):
    """NaN/None -> 0.0 (a '-' in the report means zero). `x or 0` is not enough: `nan or 0` is nan."""
    return 0.0 if x is None or pd.isna(x) else x


def find(pattern, text, group=1):
    m = re.search(pattern, text)
    return m.group(group) if m else None


def text_of(pdf: Path) -> str:
    return re.sub(r"\s+", " ", "".join((p.extract_text() or "") for p in pypdf.PdfReader(pdf).pages))


AMOUNT = r"(-?\$\s?-?\(?[\d,]+\.\d{2}\)?|-)"
REVENUE_CATEGORIES = {
    "Memberships": r"Memberships?",
    "Casual Ridership": r"Casual Riderships?",
    "Overages": r"Overages",
    "Ebike Surcharges & Other Fees": r"Ebike Surcharges & Other Fees",
    "Classic Bike Refunds & Discounts": r"Classic Bike Refunds & Discounts",
    "Ebike Refunds & Discounts": r"Ebike Refunds & Discounts",
    "Tax": r"Tax",
    "Sponsorship": r"Sponsorship",
    "Lyft Pink": r"Lyft Pink",
    "TOTAL": r"TOTAL",
}


def extract(month: str, pdf: Path):
    t = text_of(pdf)
    ops = {
        "month": month,
        "source_file": pdf.name,
        "total_annual_members": to_num(find(rf"Total annual membership stands at {NUM}", t)),
        "report_mentions_jersey_city": "Jersey City billing zip" in t,
        "annual_signups_or_renewals": to_num(find(rf"{NUM} annual members and {NUM} casual members signed up", t)),
        "trips_total": to_num(find(rf"There were {NUM} trips in", t)),
        "trips_member": to_num(find(rf"recording {NUM} trips, compared to", t)),
        "trips_casual": to_num(find(rf"compared to {NUM} trip ?s by casual", t)),
        "avg_trip_minutes": None,
        "active_stations": to_num(find(rf"There were {NUM} active stations", t)),
        "avg_fleet": to_num(find(rf"average bike fleet last month was {NUM}", t)),
        "cs_calls": to_num(find(rf"there were {NUM} total customer service calls", t)),
        "cs_emails_webforms": to_num(find(rf"received {NUM} emails", t)),
        "cs_calls_per_100_rides": to_num(find(rf"approximately {NUM} calls per 100 rides", t)),
        "cs_avg_handle_minutes": None,
    }
    m = re.search(r"average trip lasted (\d+) minutes? ?(\d+) ?seconds", t)
    if m:
        ops["avg_trip_minutes"] = round(int(m.group(1)) + int(m.group(2)) / 60, 2)
    m = re.search(r"average time to handle a call was (\d+) minutes? ?(\d+) ?seconds", t)
    if m:
        ops["cs_avg_handle_minutes"] = round(int(m.group(1)) + int(m.group(2)) / 60, 2)

    passes = []
    seg = find(r"purchased or renewed (.*?) in [A-Z][a-z]+\.", t)
    if seg:
        for qty, kind in re.findall(r"([\d,]+) ((?:annual|single-trip|single-day|three-day) passes)", seg):
            passes.append({"month": month, "pass_type": kind.replace(" passes", ""), "quantity": to_num(qty),
                           "source_file": pdf.name})

    revenue = []
    block = find(r"Revenue Categories (.*?)TOTAL", t)
    if block:
        block += "TOTAL" + t.split("Revenue Categories", 1)[1].split("TOTAL", 1)[1][:40]
        for cat, pat in REVENUE_CATEGORIES.items():
            # first amount after the label = month-to-date column, second = year-to-date column
            m = re.search(rf"\b{pat}\s+{AMOUNT}(?:\s+{AMOUNT})?", block)
            revenue.append({"month": month, "category": cat,
                            "amount_mtd_usd": money(m.group(1)) if m else None,
                            "amount_ytd_usd": money(m.group(2)) if m and m.group(2) else None,
                            "basis": "reported", "found": bool(m), "source_file": pdf.name})
    return ops, passes, revenue


def ytd_before(rev, month):
    """Rows of the month before `month`, indexed by category (their YTD column is the YTD at the end of
    that month). Returns None in January, where the earlier YTD is 0 by definition."""
    y, mo = month.split("-")
    if mo == "01":
        return None
    prev = f"{y}-{int(mo) - 1:02d}"
    return rev[rev.month == prev].set_index("category")


def check_ytd(rev):
    """For each published month: YTD - MTD must equal last month's YTD (January: YTD = MTD).
    An MTD reported as '-' counts as 0; rows without a YTD value are skipped (nothing to test)."""
    rows = []
    for (month, cat), r in rev.set_index(["month", "category"]).iterrows():
        prev = ytd_before(rev, month)
        if prev is not None and (prev.empty or cat not in prev.index):
            continue  # previous report not published
        expected = 0.0 if prev is None else prev.loc[cat, "amount_ytd_usd"]
        if pd.isna(r.amount_ytd_usd) or pd.isna(expected):
            continue
        got = r.amount_ytd_usd - nz(r.amount_mtd_usd)
        rows.append({"month": month, "category": cat, "ytd_minus_mtd": round(got, 2),
                     "previous_ytd": round(expected, 2), "difference": round(got - expected, 2)})
    cols = ["month", "category", "ytd_minus_mtd", "previous_ytd", "difference"]
    return pd.DataFrame(rows, columns=cols).sort_values(["month", "category"], ignore_index=True)


def derive_missing(rev, missing):
    """Revenue for an unpublished month, calculated (not estimated) from the published year-to-date columns:
    month m = (YTD at the end of m+1 - month m+1) - YTD at the end of m-1. Needs m-1 and m+1 published,
    in the same calendar year (in January the earlier YTD is 0)."""
    out = []
    for m in missing:
        y, mo = m.split("-")
        nxt = f"{y}-{int(mo) + 1:02d}"
        after = rev[rev.month == nxt].set_index("category")
        before = ytd_before(rev, m)
        if mo == "12" or after.empty or (before is not None and before.empty):
            continue  # cannot be calculated; stays NULL
        for cat in after.index:
            if pd.isna(after.loc[cat, "amount_ytd_usd"]):
                continue  # reported as '-'
            ytd_end = after.loc[cat, "amount_ytd_usd"] - nz(after.loc[cat, "amount_mtd_usd"])
            ytd_start = 0.0 if before is None else nz(before.loc[cat, "amount_ytd_usd"])
            files = {after.loc[cat, "source_file"]}
            if before is not None:
                files.add(before.loc[cat, "source_file"])
            out.append({"month": m, "category": cat, "amount_mtd_usd": round(ytd_end - ytd_start, 2),
                        "amount_ytd_usd": round(ytd_end, 2), "basis": "derived_from_ytd", "found": True,
                        "source_file": "; ".join(sorted(files))})
    return pd.DataFrame(out)


def main() -> None:
    index = pd.read_csv(REPORTS / "report_index.csv")
    ops_rows, pass_rows, rev_rows = [], [], []
    for r in index.itertuples():
        o, p, v = extract(r.month, REPORTS / r.file)
        ops_rows.append(o)
        pass_rows.extend(p)
        rev_rows.extend(v)
    missing = [m.strip() for m in (REPORTS / "missing_reports.txt").read_text().split() if m.strip()]
    for m in missing:  # unpublished months stay as empty rows, never filled
        ops_rows.append({"month": m, "source_file": None})
    ops = pd.DataFrame(ops_rows).sort_values("month")
    passes, rev = pd.DataFrame(pass_rows), pd.DataFrame(rev_rows)
    ytd_checks = check_ytd(rev)
    derived = derive_missing(rev, missing)
    rev = pd.concat([rev, derived], ignore_index=True).sort_values(["month", "category"])

    # consistency checks written next to the data
    issues = []
    for o in ops.itertuples():
        if pd.isna(o.source_file):
            issues.append((o.month, "report not published", ""))
            continue
        for col in ["total_annual_members", "trips_total", "trips_member", "trips_casual", "cs_calls"]:
            if pd.isna(getattr(o, col)):
                issues.append((o.month, f"{col} not found", o.source_file))
        if not pd.isna(o.trips_member) and not pd.isna(o.trips_total):
            diff = o.trips_total - o.trips_member - o.trips_casual
            if abs(diff) > 1:
                issues.append((o.month, f"member+casual != total trips (diff {diff:,.0f})", o.source_file))
    for m, g in rev.groupby("month"):
        tot = g.loc[g.category == "TOTAL", "amount_mtd_usd"].iloc[0]
        parts = g.loc[g.category != "TOTAL", "amount_mtd_usd"].fillna(0).sum()
        if tot is None or pd.isna(tot) or abs(tot - parts) > 1:
            issues.append((m, f"revenue categories sum {parts:,.2f} != TOTAL {tot}", g.source_file.iloc[0]))
    not_found = rev[~rev.found & (rev.category != "Overages")]
    for x in not_found.itertuples():
        issues.append((x.month, f"revenue category '{x.category}' not found", x.source_file))

    ops.to_csv(STAGING / "nyc_monthly_operations.csv", index=False)
    passes.to_csv(STAGING / "nyc_pass_sales.csv", index=False)
    rev.drop(columns="found").to_csv(STAGING / "nyc_revenue.csv", index=False)
    ytd_checks.to_csv(ROOT / "qa" / "revenue_ytd_checks.csv", index=False)  # differences = Citi Bike's own corrections
    bad = ytd_checks[ytd_checks.difference.abs() > 1]
    pd.DataFrame(issues, columns=["month", "issue", "source_file"]).to_csv(
        ROOT / "qa" / "report_extraction_issues.csv", index=False)
    print(f"{len(ops)} months ({len(missing)} unpublished), {len(passes)} pass rows, {len(rev)} revenue rows "
          f"({len(derived)} derived from YTD), {len(ytd_checks)} YTD checks ({len(bad)} show later corrections), "
          f"{len(issues)} issues")


if __name__ == "__main__":
    main()
