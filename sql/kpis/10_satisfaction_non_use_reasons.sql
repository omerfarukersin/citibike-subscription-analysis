-- KPI category: SATISFACTION / ACQUISITION barriers (NYC, survey 2024)
-- Share of CYCLISTS who do not use Citi Bike (never, or not in the last 12 months) citing each reason.
-- (Non-cyclists were not asked; see 05_engagement_survey_frequency.sql.)
-- Multiple reasons allowed, so shares do not sum to 100%. Weighted.
-- Source tables: survey_non_use_reason, survey_respondent, survey_code
CREATE OR REPLACE VIEW kpi_non_use_reasons AS
WITH non_users AS (
    SELECT person_id, person_weight FROM survey_respondent
    WHERE citi_bike_freq_code IN (1, 2) AND person_weight > 0
)
SELECT nr.reason_code,
       c.label AS reason,
       count(*) AS respondents_n,
       sum(n.person_weight) / (SELECT sum(person_weight) FROM non_users) AS weighted_share_of_non_users
FROM survey_non_use_reason nr
JOIN non_users n USING (person_id)
JOIN survey_code c ON c.variable = 'non_use_reason' AND c.code = nr.reason_code
GROUP BY ALL
ORDER BY weighted_share_of_non_users DESC;
