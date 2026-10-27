-- KPI category: SATISFACTION (NYC, operational proxy)
-- Support contacts per 100 trips and phone handling time. No NPS/CSAT is published.
-- Source tables: support_contacts, monthly_operations
CREATE OR REPLACE VIEW kpi_support_monthly AS
SELECT o.year_month,
       max(s.contacts) FILTER (WHERE s.channel = 'phone')          AS phone_calls,
       max(s.contacts) FILTER (WHERE s.channel = 'email/web form') AS emails_webforms,
       max(s.avg_handle_minutes) FILTER (WHERE s.channel = 'phone') AS avg_handle_minutes,
       100.0 * max(s.contacts) FILTER (WHERE s.channel = 'phone') / o.trips_total AS calls_per_100_trips
FROM monthly_operations o
JOIN support_contacts s USING (city_id, year_month)
WHERE o.city_id = 'NYC'
GROUP BY o.year_month, o.trips_total
ORDER BY o.year_month;
