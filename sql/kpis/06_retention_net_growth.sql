-- KPI category: RETENTION (NYC)
-- Net membership growth (month-on-month and year-on-year). True churn is NOT computed because the reports
-- combine new sign-ups and renewals in one figure. Months without a report stay NULL.
-- report_scope_changed marks the months from Mar 2025, when the report's TRIP totals started to include
-- Jersey City/Hoboken (monthly_operations.trips_include_jersey_city). It is reused here as a definition-break
-- flag: in the same month the member-count sentence stopped mentioning Jersey City billing zip codes, and
-- the reports do not say whether the member definition changed. Read MoM/YoY growth across Mar 2025 with care.
-- Source tables: monthly_operations
CREATE OR REPLACE VIEW kpi_retention_net_growth AS
SELECT year_month, total_annual_members, trips_include_jersey_city AS report_scope_changed,
       total_annual_members - lag(total_annual_members) OVER w        AS net_change_mom,
       total_annual_members / lag(total_annual_members) OVER w - 1    AS net_growth_mom,
       total_annual_members / lag(total_annual_members, 12) OVER w - 1 AS net_growth_yoy
FROM monthly_operations
WHERE city_id = 'NYC'
WINDOW w AS (ORDER BY year_month)
ORDER BY year_month;
