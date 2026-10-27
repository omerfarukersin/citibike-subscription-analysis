-- HYPOTHESIS H1: Casual riders are more weather-sensitive than members.
-- Method: each day's trips are divided by the average for the same city, rider type, month of the same year
-- (year_month) and weekday/weekend type ("baseline"). A ratio of 0.80 = 20% fewer trips than a normal
-- comparable day. Each day is part of its own baseline, which slightly understates the effects (conservative).
-- This removes season and weekday effects; remaining differences are ASSOCIATED with weather.
-- Holidays are excluded from the baseline comparison.
-- Weather bands: a NULL reading gets '0 Unknown' instead of falling into the last band.
-- Source tables: daily_ridership (NYC: BTS; CHI: Divvy trip files), weather_daily (NOAA), calendar_date
CREATE OR REPLACE VIEW h1_daily_weather_ridership AS
SELECT d.city_id, d.date, c.year_month, c.season, c.day_of_week, c.is_weekend, c.is_holiday,
       d.rider_type, d.trips,
       d.trips / avg(d.trips) FILTER (WHERE NOT c.is_holiday)
                 OVER (PARTITION BY d.city_id, d.rider_type, c.year_month, c.is_weekend) AS trips_vs_baseline,
       w.tmax_c, w.tmin_c, w.precip_mm, w.snow_mm, w.wind_ms,
       CASE WHEN w.precip_mm IS NULL THEN '0 Unknown'
            WHEN w.precip_mm = 0 THEN '1 Dry'
            WHEN w.precip_mm < 5 THEN '2 Light (<5 mm)'
            WHEN w.precip_mm < 20 THEN '3 Moderate (5-20 mm)'
            ELSE '4 Heavy (20+ mm)' END AS rain_band,
       CASE WHEN w.tmax_c IS NULL THEN '0 Unknown'
            WHEN w.tmax_c < 0 THEN '1 Below 0°C'
            WHEN w.tmax_c < 10 THEN '2 0-10°C'
            WHEN w.tmax_c < 20 THEN '3 10-20°C'
            WHEN w.tmax_c < 30 THEN '4 20-30°C'
            ELSE '5 30°C+' END AS temp_band,
       w.snow_mm > 0 AS snow_day
FROM daily_ridership d
JOIN calendar_date c USING (date)
JOIN weather_daily w USING (city_id, date);

CREATE OR REPLACE VIEW h1_rain_effect AS
SELECT city_id, rider_type, rain_band, count(*) AS days,
       avg(trips_vs_baseline) AS avg_trips_vs_baseline
FROM h1_daily_weather_ridership WHERE NOT is_holiday
GROUP BY ALL ORDER BY city_id, rider_type, rain_band;

-- Raw averages by temperature band: these INCLUDE the seasonal effect (cold days are winter days).
-- Use h1_rain_effect / h1_snow_effect for weather effects net of season.
CREATE OR REPLACE VIEW h1_temperature_effect AS
SELECT city_id, rider_type, temp_band, count(*) AS days,
       avg(trips) AS avg_daily_trips
FROM h1_daily_weather_ridership WHERE NOT is_holiday
GROUP BY ALL ORDER BY city_id, rider_type, temp_band;

CREATE OR REPLACE VIEW h1_snow_effect AS
SELECT city_id, rider_type, snow_day, count(*) AS days,
       avg(trips_vs_baseline) AS avg_trips_vs_baseline
FROM h1_daily_weather_ridership WHERE NOT is_holiday AND season = 'Winter'
GROUP BY ALL ORDER BY city_id, rider_type, snow_day;
