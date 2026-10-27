-- Recommendation checks: the figures behind the three recommendations in README.md and docs/project_report.md.
--
-- NOT part of the `make` pipeline. These are ad-hoc, read-only queries against the finished database.
-- They use only base tables (daily_ridership, weather_daily, calendar_date, revenue), so they do not
-- depend on any view or mart column name. Run with the DuckDB CLI:
--   duckdb -readonly citibike.duckdb < sql/analysis/recommendation_checks.sql
-- or paste each query into duckdb.connect('citibike.duckdb', read_only=True).sql(...) from Python.
--
-- Normal-day baseline (same definition as sql/kpis/11_h1_weather_sensitivity.sql):
--   baseline = average daily trips for the same city, rider type, calendar month (year_month) and
--   weekday/weekend type, computed over non-holiday days only. ratio = trips / baseline.
-- All results are associations, not causes.


-- 1. Warm winter days ------------------------------------------------------------------------------------------
-- Definitions:
--   winter day      = a day in Dec, Jan or Feb (calendar_date.season = 'Winter'), all three winters in the window
--   usual max temp  = the city's mean daily maximum temperature for that calendar month (Dec, Jan or Feb),
--                     averaged over the three winters in the window
--   warm winter day = daily max temperature at least 8 °C above the usual max temp for its city and month
--   dry             = precip_mm = 0
--   holidays are excluded, as in the H1 views
-- Output: number of such days and the simple average of trips / baseline by rider type, for both cities
-- together (city_id = NULL) and for each city.
WITH base AS (
    SELECT d.city_id, d.date, d.rider_type, d.trips, c.season, c.is_holiday,
           avg(d.trips) FILTER (WHERE NOT c.is_holiday)
               OVER (PARTITION BY d.city_id, d.rider_type, c.year_month, c.is_weekend) AS baseline
    FROM daily_ridership d
    JOIN calendar_date c USING (date)
),
winter_weather AS (
    SELECT w.city_id, w.date, w.precip_mm,
           w.tmax_c - avg(w.tmax_c) OVER (PARTITION BY w.city_id, month(w.date)) AS tmax_anomaly_c
    FROM weather_daily w
    JOIN calendar_date c USING (date)
    WHERE c.season = 'Winter'
)
SELECT b.city_id,
       count(DISTINCT b.date)                                                      AS warm_dry_days,
       round(avg(b.trips / b.baseline) FILTER (WHERE b.rider_type = 'casual'), 2)  AS casual_vs_normal_day,
       round(avg(b.trips / b.baseline) FILTER (WHERE b.rider_type = 'member'), 2)  AS member_vs_normal_day
FROM base b
JOIN winter_weather w USING (city_id, date)
WHERE w.tmax_anomaly_c >= 8
  AND w.precip_mm = 0
  AND NOT b.is_holiday
GROUP BY ROLLUP (b.city_id)
ORDER BY b.city_id NULLS FIRST;


-- 2. Snow on the ground vs snowfall days, New York, winter 2025-26 ---------------------------------------------
-- Definitions:
--   window            = 1 Dec 2025 to 28 Feb 2026, New York only, every day (holidays included, because this is
--                       a total of lost trips over the whole winter)
--   snowfall day      = snow_mm > 0
--   dry day with snow still on the ground = snow_mm = 0, precip_mm < 1 and snow_depth_mm > 0
--   trips vs normal   = sum(trips) / sum(baseline), members and casual riders together (trip-weighted)
--   trips below normal = sum(baseline - trips)
WITH base AS (
    SELECT d.city_id, d.date, d.rider_type, d.trips,
           avg(d.trips) FILTER (WHERE NOT c.is_holiday)
               OVER (PARTITION BY d.city_id, d.rider_type, c.year_month, c.is_weekend) AS baseline
    FROM daily_ridership d
    JOIN calendar_date c USING (date)
)
SELECT CASE WHEN w.snow_mm > 0 THEN 'snowfall day'
            WHEN w.precip_mm < 1 AND w.snow_depth_mm > 0 THEN 'dry, snow on the ground'
            ELSE 'other winter day' END                       AS day_type,
       count(DISTINCT b.date)                                 AS n_days,
       round(100 * sum(b.trips) / sum(b.baseline), 1)         AS pct_of_normal_trips,
       round(sum(b.baseline - b.trips))                       AS trips_below_normal
FROM base b
JOIN weather_daily w USING (city_id, date)
WHERE b.city_id = 'NYC'
  AND b.date BETWEEN DATE '2025-12-01' AND DATE '2026-02-28'
GROUP BY 1
ORDER BY 1;


-- 3. Revenue per trip by rider type, New York, Jul 2025 - Jun 2026 ---------------------------------------------
-- Definitions:
--   casual revenue     = report category 'Casual Ridership' (single rides and day passes)
--   membership revenue = 'Memberships' + 'Lyft Pink'
--   'Ebike Surcharges & Other Fees' is not split by rider type in the reports, so it is left out of both.
--   trips              = BTS daily ridership, New York only, by rider type
-- Caveat: from March 2025 the report totals include Jersey City and Hoboken while BTS trips are New York only,
-- so both per-trip figures are overstated by up to about 2.5%. The ratio between them is unaffected.
WITH rev AS (
    SELECT sum(amount_mtd_usd) FILTER (WHERE category = 'Casual Ridership')               AS casual_revenue,
           sum(amount_mtd_usd) FILTER (WHERE category IN ('Memberships', 'Lyft Pink'))     AS membership_revenue
    FROM revenue
    WHERE city_id = 'NYC' AND year_month BETWEEN '2025-07' AND '2026-06'
),
trips AS (
    SELECT sum(trips) FILTER (WHERE rider_type = 'casual') AS casual_trips,
           sum(trips) FILTER (WHERE rider_type = 'member') AS member_trips
    FROM daily_ridership
    WHERE city_id = 'NYC' AND date BETWEEN DATE '2025-07-01' AND DATE '2026-06-30'
)
SELECT round(casual_revenue / casual_trips, 2)                                         AS casual_fees_per_casual_trip,
       round(membership_revenue / member_trips, 2)                                     AS membership_revenue_per_member_trip,
       round((casual_revenue / casual_trips) / (membership_revenue / member_trips), 1) AS ratio
FROM rev, trips;
