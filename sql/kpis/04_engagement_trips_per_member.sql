-- KPI category: ENGAGEMENT (NYC)
-- Trips per annual member per month = member trips / total annual members (both from the same report).
-- Caveat: from Mar 2025 the report's member trips include Jersey City/Hoboken (scope break).
-- Source tables: monthly_operations
CREATE OR REPLACE VIEW kpi_trips_per_member AS
SELECT year_month, trips_member, total_annual_members, trips_include_jersey_city,
       trips_member / total_annual_members AS trips_per_member
FROM monthly_operations
WHERE city_id = 'NYC' AND report_published
ORDER BY year_month;
