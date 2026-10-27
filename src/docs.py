"""Generate docs/data_dictionary.md and docs/erd.mmd (Mermaid) from the live database,
so the documentation always matches the real tables, keys and row counts."""
import re
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
TABLE_SOURCE = {
    "city": "Project configuration (NOAA station IDs from NOAA GHCN-Daily)",
    "calendar_date": "Generated; US federal holidays from pandas USFederalHolidayCalendar",
    "rider_type": "Project definition (member = subscription, casual = pay as you go)",
    "plan": "Citi Bike / Divvy pricing pages; survey access options; report pass types",
    "plan_price": "Citi Bike / Divvy pricing pages (Wayback snapshots + live), Citi Bike price-change notice",
    "station": "Trip files (sample months)",
    "weather_daily": "NOAA GHCN-Daily (Central Park, O'Hare)",
    "daily_ridership": "NYC: BTS Docked Bikeshare Ridership; Chicago: Divvy trip files (all months)",
    "qa_bts_daily": "BTS Docked Bikeshare Ridership (cross-check only)",
    "qa_bts_jersey_city_daily": "BTS Docked Bikeshare Ridership, Citi Bike Jersey City (cross-check only)",
    "monthly_operations": "Citi Bike monthly operating reports (PDF)",
    "support_contacts": "Citi Bike monthly operating reports (PDF)",
    "pass_sales": "Citi Bike monthly operating reports (PDF)",
    "revenue": "Citi Bike monthly operating reports (PDF), month-to-date, preliminary/unaudited; "
               "Feb and May 2026 calculated from neighbouring reports' year-to-date columns",
    "trip_sample": "Citi Bike + Divvy trip files: Jul 2025, Oct 2025, Jan 2026, Apr 2026",
    "survey_code": "NYC DOT Citywide Mobility Survey 2024 data dictionary",
    "survey_respondent": "NYC DOT Citywide Mobility Survey 2024, Person table",
    "survey_plan_held": "NYC DOT Citywide Mobility Survey 2024 (citi_bike_pay)",
    "survey_non_use_reason": "NYC DOT Citywide Mobility Survey 2024 (no_bike_share_1..8)",
}


def column_comments() -> dict:
    """Inline '-- comment' after each column in schema.sql."""
    out, table = {}, None
    for line in (ROOT / "sql" / "schema.sql").read_text().splitlines():
        m = re.match(r"CREATE TABLE (\w+)", line)
        if m:
            table = m.group(1)
        m = re.match(r"\s+(\w+)\s+[A-Z].*?--\s*(.+)$", line)
        if table and m:
            out[(table, m.group(1))] = m.group(2).strip()
    return out


def main() -> None:
    con = duckdb.connect(str(ROOT / "citibike.duckdb"), read_only=True)
    comments = column_comments()
    tables = [t for (t,) in con.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_type = 'BASE TABLE' ORDER BY 1").fetchall()]
    pks = {(r[0], c) for r in con.execute(
        "SELECT table_name, constraint_column_names FROM duckdb_constraints() WHERE constraint_type = 'PRIMARY KEY'"
    ).fetchall() for c in r[1]}
    fks = con.execute("""SELECT table_name, constraint_column_names, referenced_table, referenced_column_names
                         FROM duckdb_constraints() WHERE constraint_type = 'FOREIGN KEY'""").fetchall()
    fk_cols = {(t, c) for t, cols, _, _ in fks for c in cols}

    md = ["# Data dictionary", "",
          "Generated from `citibike.duckdb` by `src/docs.py`. PK = primary key, FK = foreign key.", ""]
    mmd = ["erDiagram"]
    for t in tables:
        n = con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        md += [f"## `{t}` ({n:,} rows)", "", f"Source: {TABLE_SOURCE.get(t, '')}", "",
               "| Column | Type | Key | Description |", "|---|---|---|---|"]
        mmd.append(f"    {t} {{")
        for col, typ in con.execute(f"""SELECT column_name, data_type FROM information_schema.columns
                                         WHERE table_name = '{t}' ORDER BY ordinal_position""").fetchall():
            key = ", ".join(k for k, s in (("PK", pks), ("FK", fk_cols)) if (t, col) in s)
            md.append(f"| `{col}` | {typ} | {key} | {comments.get((t, col), '')} |")
            mtyp = re.sub(r"\W", "_", typ.split("(")[0])
            mmd.append(f"        {mtyp} {col}{' ' + key if key else ''}")
        mmd.append("    }")
        md.append("")
    seen = set()
    for t, cols, ref, _ in fks:
        if (ref, t) not in seen:
            seen.add((ref, t))
            mmd.append(f'    {ref} ||--o{{ {t} : "{",".join(cols)}"')
    (ROOT / "docs" / "data_dictionary.md").write_text("\n".join(md))
    (ROOT / "docs" / "erd.mmd").write_text("\n".join(mmd) + "\n")
    print(f"documented {len(tables)} tables, {len(fks)} foreign keys")


if __name__ == "__main__":
    main()
