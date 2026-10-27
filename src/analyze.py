"""Create KPI / hypothesis / QA views in citibike.duckdb and export:
  data/marts/*.csv  small tables for Tableau Public
  qa/*.csv          validation results
"""
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
MARTS = ROOT / "data" / "marts"
QA = ROOT / "qa"

EXPORTS = {  # mart file -> query
    "nyc_monthly_kpis": """
        SELECT a.year_month, strptime(a.year_month || '-01', '%Y-%m-%d')::DATE AS month_start,
               a.annual_signups_or_renewals, a.single_trip_passes, a.day_passes,
               r.total_annual_members, r.net_change_mom, r.net_growth_yoy, r.report_scope_changed,
               t.trips_member, t.trips_per_member,
               m.total_revenue, m.revenue_before_tax, m.revenue_basis, m.rider_revenue, m.membership_revenue,
               m.lyft_pink_revenue, m.membership_sales_per_member, m.rider_revenue_per_trip, m.annual_list_price,
               m.days_since_price_observation, m.list_price_mrr, m.list_price_arr,
               s.phone_calls, s.emails_webforms, s.avg_handle_minutes, s.calls_per_100_trips
        FROM kpi_acquisition_monthly a
        LEFT JOIN kpi_retention_net_growth r USING (year_month)
        LEFT JOIN kpi_trips_per_member t USING (year_month)
        LEFT JOIN kpi_monetization_monthly m USING (year_month)
        LEFT JOIN kpi_support_monthly s USING (year_month)
        ORDER BY year_month""",
    "nyc_revenue_mix": "SELECT year_month, strptime(year_month || '-01', '%Y-%m-%d')::DATE AS month_start, "
                       "* EXCLUDE (year_month) FROM kpi_revenue_mix ORDER BY year_month, category",
    "city_monthly_engagement": "SELECT city_id, year_month, "
                               "strptime(year_month || '-01', '%Y-%m-%d')::DATE AS month_start, "
                               "* EXCLUDE (city_id, year_month) FROM kpi_engagement_monthly",
    "daily_weather_ridership": "SELECT *, CASE WHEN month(date) >= 7 THEN year(date) || '-' || (year(date) + 1) "
                               "ELSE (year(date) - 1) || '-' || year(date) END AS ride_year "
                               "FROM h1_daily_weather_ridership ORDER BY city_id, date, rider_type",
    "weather_rain_effect": "SELECT * FROM h1_rain_effect",
    "weather_temperature_effect": "SELECT * FROM h1_temperature_effect",
    "weather_snow_effect": "SELECT * FROM h1_snow_effect",
    "seasonality": "SELECT * FROM h2_seasonality",
    "city_comparison": "SELECT * FROM h3_city_comparison",
    "price_history": "SELECT * FROM kpi_price_comparison",
    "price_breakeven": "SELECT * FROM kpi_price_breakeven",
    "ebike_share": "SELECT * FROM h4_ebike_share",
    "station_activity": "SELECT * FROM station_activity WHERE total_trips >= 10 ORDER BY station_key",
    "survey_plan_held": "SELECT * FROM kpi_survey_plan_held",
    "survey_frequency": "SELECT * FROM kpi_survey_frequency",
    "survey_non_use_reasons": "SELECT * FROM kpi_non_use_reasons",
}
QA_EXPORTS = ["qa_report_vs_bts", "qa_sample_vs_bts", "qa_trip_quality", "qa_completeness", "qa_chi_files_vs_bts",
              "qa_report_vs_bts_jc"]


def export(con, query, path):
    """Write a query result as CSV with deterministic output: fixed row order and 10-decimal rounding
    (parallel sums differ in the 16th digit). Every view used here has an ORDER BY; the sort is a safety net."""
    df = con.execute(query).df()
    if "ORDER BY" not in query:
        df = df.sort_values(list(df.columns), kind="stable")
    num = df.select_dtypes("float").columns
    df[num] = df[num].round(10)
    df.to_csv(path, index=False)
    return df


def main() -> None:
    con = duckdb.connect(str(ROOT / "citibike.duckdb"))
    for sql in sorted((ROOT / "sql" / "kpis").glob("*.sql")):
        con.execute(sql.read_text())
    con.execute((ROOT / "sql" / "qa_checks.sql").read_text())
    MARTS.mkdir(parents=True, exist_ok=True)
    for name, query in EXPORTS.items():
        df = export(con, query, MARTS / f"{name}.csv")
        print(f"mart {name:28s} {len(df):>6,} rows")
    for view in QA_EXPORTS:
        export(con, f"SELECT * FROM {view}", QA / f"{view}.csv")
    con.close()


if __name__ == "__main__":
    main()
