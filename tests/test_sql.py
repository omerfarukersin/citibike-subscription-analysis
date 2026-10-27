from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]


def test_schema_and_views_compile_on_empty_db():
    con = duckdb.connect()
    con.execute((ROOT / "sql" / "schema.sql").read_text())
    for f in sorted((ROOT / "sql" / "kpis").glob("*.sql")):
        con.execute(f.read_text())
    con.execute((ROOT / "sql" / "qa_checks.sql").read_text())
    tables = con.execute("SELECT count(*) FROM duckdb_tables()").fetchone()[0]
    fks = con.execute("SELECT count(*) FROM duckdb_constraints() WHERE constraint_type = 'FOREIGN KEY'").fetchone()[0]
    assert (tables, fks) == (19, 28)
    for (v,) in con.execute("SELECT view_name FROM duckdb_views() WHERE NOT internal").fetchall():
        con.execute(f"SELECT * FROM {v} LIMIT 0")
