-- HYPOTHESIS H4: E-bike use differs between members and casual riders (trip sample: Jul 2025, Oct 2025,
-- Jan 2026, Apr 2026). Valid trips only, BTS rule: 1-120 min; NYC also requires both stations
-- (Divvy allows parking outside stations).
-- Source tables: trip_sample, calendar_date
CREATE OR REPLACE VIEW h4_ebike_share AS
SELECT t.city_id, c.year_month, t.rider_type,
       count(*) AS trips,
       avg((t.rideable_type = 'electric_bike')::INT) AS ebike_share,
       median(t.duration_min) FILTER (WHERE t.rideable_type = 'electric_bike') AS ebike_median_min,
       median(t.duration_min) FILTER (WHERE t.rideable_type = 'classic_bike')  AS classic_median_min
FROM trip_sample t JOIN calendar_date c USING (date)
WHERE t.is_valid AND c.year_month IN ('2025-07', '2025-10', '2026-01', '2026-04')
GROUP BY ALL ORDER BY t.city_id, c.year_month, t.rider_type;

-- Station-level activity for the Tableau map (sample months, valid trips)
CREATE OR REPLACE VIEW station_activity AS
SELECT s.city_id, s.station_key, s.station_name, s.lat, s.lng,
       count(*) FILTER (WHERE t.rider_type = 'member') AS member_trips,
       count(*) FILTER (WHERE t.rider_type = 'casual') AS casual_trips,
       count(*) AS total_trips,
       count(*) FILTER (WHERE t.rider_type = 'member') / count(*) AS member_share
FROM trip_sample t JOIN station s ON s.station_key = t.start_station_key
WHERE t.is_valid
GROUP BY ALL;
