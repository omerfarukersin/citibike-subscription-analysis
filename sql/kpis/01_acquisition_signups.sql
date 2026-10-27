-- KPI category: ACQUISITION (NYC)
-- Monthly annual-membership sign-ups or renewals and passes sold, with year-on-year change.
-- Note: the reports combine new and renewing members in one figure.
-- Source tables: monthly_operations, pass_sales (NYC only; it has no city_id)
CREATE OR REPLACE VIEW kpi_acquisition_monthly AS
SELECT o.year_month,
       o.annual_signups_or_renewals,
       max(CASE WHEN s.plan_id = 'NYC_SINGLE' THEN s.quantity END)  AS single_trip_passes,
       max(CASE WHEN s.plan_id = 'NYC_DAY' THEN s.quantity END)     AS day_passes,
       o.annual_signups_or_renewals
         / NULLIF(lag(o.annual_signups_or_renewals, 12) OVER (ORDER BY o.year_month), 0) - 1 AS signups_yoy_change
FROM monthly_operations o
LEFT JOIN pass_sales s ON s.year_month = o.year_month
WHERE o.city_id = 'NYC'
GROUP BY o.year_month, o.annual_signups_or_renewals
ORDER BY o.year_month;
