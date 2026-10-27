-- KPI category: ACQUISITION (NYC, survey 2024)
-- How Citi Bike users (used in the last 12 months) last accessed the service = plan / acquisition channel.
-- Weighted with person_weight (citywide adults); n = unweighted respondents.
-- Source tables: survey_plan_held, survey_respondent, survey_code, plan
CREATE OR REPLACE VIEW kpi_survey_plan_held AS
SELECT h.access_code,
       c.label                         AS access_method,
       coalesce(pl.plan_name, 'Other') AS plan_name,   -- label for access_code 997 ('Other')
       CASE WHEN pl.is_subscription IS NULL THEN 'Not stated' WHEN pl.is_subscription THEN 'Yes' ELSE 'No' END AS is_subscription,  -- 'Other' is not classified in the source
       count(*)                        AS respondents_n,
       sum(r.person_weight)            AS weighted_persons,
       sum(r.person_weight) / sum(sum(r.person_weight)) OVER () AS weighted_share
FROM survey_plan_held h
JOIN survey_respondent r USING (person_id)
JOIN survey_code c ON c.variable = 'citi_bike_pay' AND c.code = h.access_code
LEFT JOIN plan pl ON pl.plan_id = h.plan_id
GROUP BY ALL
ORDER BY weighted_share DESC;
