-- HYPOTHESIS H3: Member share of trips differs between cities; compared alongside the price ladder.
-- (Association only: price is one of many differences between the cities.)
-- Source tables: daily_ridership, calendar_date, plan_price, plan
CREATE OR REPLACE VIEW h3_city_comparison AS
WITH y AS (
    SELECT d.city_id,
           CASE WHEN c.month >= 7 THEN c.year ELSE c.year - 1 END AS ride_year_start,
           sum(trips) FILTER (WHERE rider_type = 'member') AS member_trips,
           sum(trips) AS total_trips,
           sum(trip_minutes) FILTER (WHERE rider_type = 'member') / sum(trips) FILTER (WHERE rider_type = 'member') AS member_avg_min,
           sum(trip_minutes) FILTER (WHERE rider_type = 'casual') / sum(trips) FILTER (WHERE rider_type = 'casual') AS casual_avg_min
    FROM daily_ridership d JOIN calendar_date c USING (date)
    GROUP BY ALL
)
SELECT city_id,
       ride_year_start || '-' || (ride_year_start + 1) AS ride_year,
       total_trips, member_trips, member_trips / total_trips AS member_share,
       member_avg_min, casual_avg_min
FROM y ORDER BY city_id, ride_year_start;
