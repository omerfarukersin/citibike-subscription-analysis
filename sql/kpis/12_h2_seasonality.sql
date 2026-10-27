-- HYPOTHESIS H2: The winter drop is deeper in Chicago, and members hold up better than casual riders.
-- Winter retention ratio = average daily trips in Dec-Feb / average daily trips in Jun-Aug of the same
-- "ride year" (Jul-Jun). 1.00 = no seasonal drop.
-- Source tables: daily_ridership, calendar_date, weather_daily
CREATE OR REPLACE VIEW h2_seasonality AS
WITH d AS (
    SELECT dr.city_id, dr.rider_type, c.season, dr.trips, w.tmax_c,
           CASE WHEN c.month >= 7 THEN c.year ELSE c.year - 1 END AS ride_year_start
    FROM daily_ridership dr JOIN calendar_date c USING (date) JOIN weather_daily w USING (city_id, date)
)
SELECT city_id, rider_type,
       ride_year_start || '-' || (ride_year_start + 1) AS ride_year,
       avg(trips) FILTER (WHERE season = 'Summer') AS summer_avg_daily_trips,
       avg(trips) FILTER (WHERE season = 'Winter') AS winter_avg_daily_trips,
       avg(trips) FILTER (WHERE season = 'Winter') / avg(trips) FILTER (WHERE season = 'Summer') AS winter_to_summer_ratio,
       avg(tmax_c) FILTER (WHERE season = 'Winter') AS winter_avg_tmax_c
FROM d
GROUP BY ALL
ORDER BY city_id, rider_type, ride_year;
