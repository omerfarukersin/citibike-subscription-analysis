"""Download the Citi Bike monthly operating reports (PDF) for the analysis window.
Source page: https://www.citibikenyc.com/system-data/operating-reports
Months with no published link are recorded in data/raw/reports/missing_reports.txt (never filled).
"""
import re
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw" / "reports"
PAGE = "https://www.citibikenyc.com/system-data/operating-reports"
MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], start=1)}
ABBR = {m[:3]: i for m, i in MONTHS.items()}


def month_of(url: str):
    m = re.search(r"/nyc/([A-Za-z]+)-(\d{4})-Citi-Bike", url)
    if not m:
        return None
    name, year = m.group(1).lower(), int(m.group(2))
    mon = MONTHS.get(name) or ABBR.get(name[:3])
    return f"{year}-{mon:02d}" if mon else None


def download_frozen(index: Path) -> None:
    """Re-download exactly the reports used in the analysis (Oct 2026); reports published later are ignored."""
    rows = pd.read_csv(index)
    for r in rows.itertuples():
        dest = OUT / r.file
        if not dest.exists() or not dest.read_bytes().startswith(b"%PDF"):
            content = requests.get(r.url, timeout=120).content
            if not content.startswith(b"%PDF"):
                raise RuntimeError(f"{r.month}: not a PDF at {r.url}")
            dest.write_bytes(content)
    print(f"downloaded {len(rows)} reports listed in {index.name}")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    index = OUT / "report_index.csv"
    if index.exists():
        download_frozen(index)
        return
    html = requests.get(PAGE, timeout=60).text
    (OUT / "operating_reports_page.html").write_text(html)
    links = {}
    for url in sorted(set(re.findall(r'https?://[^" ]+\.pdf', html))):
        ym = month_of(url)
        if ym:
            links[ym] = url
    window = [p.strftime("%Y-%m") for p in pd.period_range("2023-07", "2026-06", freq="M")]
    rows, missing = [], []
    for ym in window:
        url = links.get(ym)
        if not url:
            missing.append(ym)
            continue
        dest = OUT / f"citibike_report_{ym}.pdf"
        if not dest.exists() or not dest.read_bytes().startswith(b"%PDF"):
            content = requests.get(url, timeout=120).content
            if not content.startswith(b"%PDF") and url.endswith(".pdf.pdf"):
                # the source page links Dec 2023 with a doubled extension, which returns AccessDenied
                url = url[: -len(".pdf")]
                content = requests.get(url, timeout=120).content
            if not content.startswith(b"%PDF"):
                raise RuntimeError(f"{ym}: not a PDF at {url}")
            dest.write_bytes(content)
        rows.append({"month": ym, "file": dest.name, "url": url})
    pd.DataFrame(rows).to_csv(OUT / "report_index.csv", index=False)
    (OUT / "missing_reports.txt").write_text("\n".join(missing) + "\n")
    print(f"downloaded {len(rows)} reports; missing (no link on page): {missing}")


if __name__ == "__main__":
    main()
