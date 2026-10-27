-- QA checks (results exported to qa/). Independent sources are compared against each other.

-- QA1: NYC trips, Citi Bike monthly report vs BTS calendar-month sum (two independent publishers)
CREATE OR REPLACE VIEW qa_report_vs_bts AS
SELECT o.year_month,
       o.trips_total                       AS report_trips,
       b.total_trips                       AS bts_trips,
       b.total_trips / o.trips_total - 1   AS bts_vs_report_diff,
       o.trips_member / o.trips_total      AS report_member_share,
       b.member_share                      AS bts_member_share
FROM monthly_operations o
JOIN kpi_engagement_monthly b ON b.city_id = 'NYC' AND b.year_month = o.year_month
WHERE o.report_published
ORDER BY o.year_month;

-- QA2: trip-sample valid trips (trip-sample cleaning, BTS rule) vs BTS for the same months, both cities
CREATE OR REPLACE VIEW qa_sample_vs_bts AS
SELECT t.city_id, c.year_month, t.rider_type,
       count(*) FILTER (WHERE t.is_valid) AS sample_valid_trips,
       count(*)                           AS sample_all_trips,
       b.trips                            AS bts_trips,
       count(*) FILTER (WHERE t.is_valid) / b.trips - 1 AS sample_vs_bts_diff
FROM trip_sample t
JOIN calendar_date c USING (date)
JOIN (SELECT city_id, year_month, rider_type, sum(trips) AS trips
      FROM qa_bts_daily JOIN calendar_date USING (date) GROUP BY ALL) b
  ON b.city_id = t.city_id AND b.year_month = c.year_month AND b.rider_type = t.rider_type
WHERE c.year_month IN ('2025-07', '2025-10', '2026-01', '2026-04')
GROUP BY t.city_id, c.year_month, t.rider_type, b.trips
ORDER BY 1, 2, 3;

-- QA3: data quality profile of the trip sample
CREATE OR REPLACE VIEW qa_trip_quality AS
SELECT city_id,
       count(*)                                                AS trips,
       count(*) FILTER (WHERE duration_min < 1)                AS under_1_min,
       count(*) FILTER (WHERE duration_min > 120)              AS over_120_min,
       count(*) FILTER (WHERE duration_min < 0)                AS negative_duration,
       count(*) FILTER (WHERE start_station_key IS NULL)       AS no_start_station,
       count(*) FILTER (WHERE end_station_key IS NULL)         AS no_end_station,
       count(*) FILTER (WHERE is_valid)                        AS valid_trips,
       count(*) FILTER (WHERE is_valid) / count(*)             AS valid_share
FROM trip_sample GROUP BY city_id ORDER BY city_id;

-- QA4: completeness of daily sources across the window
CREATE OR REPLACE VIEW qa_completeness AS
SELECT 'weather_daily' AS source, city_id, count(*) AS rows,
       count(*) FILTER (WHERE tmax_c IS NULL OR precip_mm IS NULL) AS rows_flagged  -- weather: NULL values
FROM weather_daily GROUP BY city_id
UNION ALL
SELECT 'daily_ridership (zero-trip days)', city_id, count(*), count(*) FILTER (WHERE trips = 0)
FROM daily_ridership GROUP BY city_id
UNION ALL
SELECT 'monthly_operations (unpublished months)', city_id, count(*), count(*) FILTER (WHERE NOT report_published)
FROM monthly_operations GROUP BY city_id
ORDER BY source, city_id;

-- QA5: Chicago, Divvy trip files (file count, BTS rule) vs BTS by month. Large gaps = BTS problems
CREATE OR REPLACE VIEW qa_chi_files_vs_bts AS
SELECT c.year_month,
       sum(d.trips) AS divvy_files_trips,
       sum(b.trips) AS bts_trips,
       sum(b.trips) / sum(d.trips) - 1 AS bts_vs_files_diff
FROM daily_ridership d
JOIN qa_bts_daily b USING (city_id, date, rider_type)
JOIN calendar_date c USING (date)
WHERE d.city_id = 'CHI'
GROUP BY c.year_month ORDER BY c.year_month;

-- QA6: Report scope change. Report trips vs BTS NYC and BTS NYC + Jersey City (Citi Bike JC system).
-- Expected: report ~= NYC before Mar 2025, ~= NYC + JC from Mar 2025.
CREATE OR REPLACE VIEW qa_report_vs_bts_jc AS
WITH jc AS (SELECT c.year_month, sum(trips) AS jc_trips
            FROM qa_bts_jersey_city_daily JOIN calendar_date c USING (date) GROUP BY 1)
SELECT q.year_month, q.report_trips, q.bts_trips AS bts_nyc_trips, jc.jc_trips AS bts_jc_trips,
       q.bts_trips / q.report_trips - 1                  AS nyc_only_vs_report,
       (q.bts_trips + jc.jc_trips) / q.report_trips - 1  AS nyc_plus_jc_vs_report,
       o.trips_include_jersey_city
FROM qa_report_vs_bts q JOIN jc USING (year_month)
JOIN monthly_operations o ON o.city_id = 'NYC' AND o.year_month = q.year_month
ORDER BY q.year_month;
