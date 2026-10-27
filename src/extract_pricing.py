"""Parse plan prices from saved pricing pages (Wayback Machine snapshots + live pages).

Each row is a price *observation* on the snapshot date, not an assumed change date.
The one exact change date available is the official Citi Bike notice (annual -> $239 effective 2026-01-28).
Output: data/staging/plan_price_observations.csv
"""
import html
import re
import shutil
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "pricing"
REFERENCE = ROOT / "data" / "reference" / "plan_price_observations.csv"

SNAPSHOTS = [  # file, city, observed date, source URL
    ("20230813184826_citibikenyc.com_pricing.html", "NYC", "2023-08-13",
     "https://web.archive.org/web/20230813184826/https://citibikenyc.com/pricing"),
    ("20240728234803_citibikenyc.com_pricing.html", "NYC", "2024-07-28",
     "https://web.archive.org/web/20240728234803/https://citibikenyc.com/pricing"),
    ("live_20261013_citibikenyc.com_pricing.html", "NYC", "2026-10-13", "https://citibikenyc.com/pricing"),
    ("20240820033613_divvybikes.com_pricing.html", "CHI", "2024-08-20",
     "https://web.archive.org/web/20240820033613/https://divvybikes.com/pricing"),
    ("20260105000943_divvybikes.com_pricing.html", "CHI", "2026-01-05",
     "https://web.archive.org/web/20260105000943/https://divvybikes.com/pricing"),
    ("live_20261013_divvybikes.com_pricing.html", "CHI", "2026-10-13", "https://divvybikes.com/pricing"),
]
# "Single Ride Day Pass <Annual name> Lyft Pink <single> $<day>/day $<annual>/year[* ($<promo>/year ...)] $<pink>/year"
PATTERN = re.compile(
    r"Single Ride Day Pass (?:Citi Bike|Divvy(?: Annual)?) Lyft Pink "
    r"(?P<single>\$[\d.]+ for 30 mins|\$1 \+ \$[\d.]+/min) "
    r"\$(?P<day>[\d.]+)/day \$(?P<annual>[\d.]+)/year\*?"
    r"(?: \(\$(?P<promo>[\d.]+)/year[^)]*\))? \$(?P<pink>[\d.]+)/year")


def page_text(path: Path) -> str:
    raw = path.read_text(errors="ignore")
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw)))


def main() -> None:
    if not RAW.exists():
        # the saved pricing pages are not redistributed; use the prices extracted from them on 13 Oct 2026
        shutil.copy(REFERENCE, ROOT / "data" / "staging" / "plan_price_observations.csv")
        print(f"{RAW} not found: copied {REFERENCE.relative_to(ROOT)}")
        return
    rows = []
    for file, city, date, url in SNAPSHOTS:
        m = PATTERN.search(page_text(RAW / file))
        if not m:
            raise RuntimeError(f"price table not found in {file}")
        single = m["single"]
        unlock = float(re.search(r"\$([\d.]+)", single).group(1))
        per_min = re.search(r"\+ \$([\d.]+)/min", single)
        base = {"city": city, "observed_date": date, "source_url": url, "source_file": file}
        rows += [
            {**base, "plan": "Single Ride", "billing_cycle": "per ride", "price_usd": unlock,
             "per_minute_usd": float(per_min.group(1)) if per_min else None},
            {**base, "plan": "Day Pass", "billing_cycle": "day", "price_usd": float(m["day"]), "per_minute_usd": None},
            {**base, "plan": "Annual Membership", "billing_cycle": "year", "price_usd": float(m["annual"]),
             "per_minute_usd": None},
            {**base, "plan": "Lyft Pink", "billing_cycle": "year", "price_usd": float(m["pink"]),
             "per_minute_usd": None},
        ]
        if m["promo"]:
            rows.append({**base, "plan": "Annual Membership (new-member offer)", "billing_cycle": "year",
                         "price_usd": float(m["promo"]), "per_minute_usd": None})
    # official change notice: exact effective date for the NYC annual price
    notice = page_text(RAW / "live_20261013_citibikenyc.com_pricechange2026.html")
    m = re.search(r"Annual Membership: Increases to \$([\d.]+)/year \(effective (\w+ \d+, \d{4})\)", notice)
    if not m:
        raise RuntimeError("price-change notice not found in live_20261013_citibikenyc.com_pricechange2026.html")
    rows.append({"city": "NYC", "observed_date": pd.to_datetime(m.group(2)).date().isoformat(),
                 "source_url": "https://citibikenyc.com/pricechange2026",
                 "source_file": "live_20261013_citibikenyc.com_pricechange2026.html",
                 "plan": "Annual Membership", "billing_cycle": "year", "price_usd": float(m.group(1)),
                 "per_minute_usd": None})
    out = pd.DataFrame(rows).sort_values(["city", "plan", "observed_date"])
    out.to_csv(ROOT / "data" / "staging" / "plan_price_observations.csv", index=False)
    print(out[["city", "plan", "observed_date", "price_usd", "per_minute_usd"]].to_string(index=False))


if __name__ == "__main__":
    main()
