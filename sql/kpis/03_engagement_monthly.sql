-- KPI category: ENGAGEMENT (NYC + CHI)
-- Calendar-month trips by rider type, member share of trips, average trip minutes.
-- Source tables: daily_ridership (NYC: BTS daily; CHI: Divvy trip files), calendar_date
CREATE OR REPLACE VIEW kpi_engagement_monthly AS
SELECT d.city_id,
       c.year_month,
       sum(trips) FILTER (WHERE rider_type = 'member') AS member_trips,
       sum(trips) FILTER (WHERE rider_type = 'casual') AS casual_trips,
       sum(trips)                                       AS total_trips,
       sum(trips) FILTER (WHERE rider_type = 'member') / sum(trips) AS member_share,
       sum(trip_minutes) FILTER (WHERE rider_type = 'member') / sum(trips) FILTER (WHERE rider_type = 'member') AS member_avg_min,
       sum(trip_minutes) FILTER (WHERE rider_type = 'casual') / sum(trips) FILTER (WHERE rider_type = 'casual') AS casual_avg_min
FROM daily_ridership d
JOIN calendar_date c USING (date)
GROUP BY ALL
ORDER BY d.city_id, c.year_month;
