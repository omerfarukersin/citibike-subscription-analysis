-- KPI category: ENGAGEMENT / RETENTION (NYC, survey 2024)
-- Weighted distribution of Citi Bike use frequency. POPULATION: adults who ride a bicycle at least a few
-- times a year (questionnaire 9.15 is only asked if bike_freq is not 'never'; about 34% of adults, weighted).
-- "Used in the past, not in last 12 months" = lapsed-user group among cyclists (retention proxy).
-- Source tables: survey_respondent, survey_code
CREATE OR REPLACE VIEW kpi_survey_frequency AS
SELECT r.citi_bike_freq_code AS freq_code,
       c.label               AS frequency,
       count(*)              AS respondents_n,
       sum(r.person_weight) / sum(sum(r.person_weight)) OVER () AS weighted_share
FROM survey_respondent r
JOIN survey_code c ON c.variable = 'citi_bike_freq' AND c.code = r.citi_bike_freq_code
WHERE r.citi_bike_freq_code <> 995 AND r.person_weight > 0
GROUP BY ALL
ORDER BY freq_code;
