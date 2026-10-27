-- KPI category: MONETIZATION (NYC vs CHI)
-- Price ladder per city at each observation, and the break-even: annual price / day-pass price
-- (how many day passes a casual rider would buy before an annual membership is cheaper).
-- Source tables: plan_price, plan
CREATE OR REPLACE VIEW kpi_price_comparison AS
SELECT pl.city_id, pp.observed_date, pl.plan_name, pl.billing_cycle, pl.is_subscription,
       pp.price_usd, pp.per_minute_usd, pp.source_url
FROM plan_price pp JOIN plan pl USING (plan_id)
ORDER BY pl.city_id, pl.plan_name, pp.observed_date;

CREATE OR REPLACE VIEW kpi_price_breakeven AS
SELECT a.city_id, a.observed_date,
       a.price_usd AS annual_price, d.price_usd AS day_pass_price,
       a.price_usd / d.price_usd AS day_passes_to_break_even
FROM (SELECT pl.city_id, pp.observed_date, pp.price_usd FROM plan_price pp JOIN plan pl USING (plan_id)
      WHERE pl.plan_name = 'Annual Membership') a
JOIN (SELECT pl.city_id, pp.observed_date, pp.price_usd FROM plan_price pp JOIN plan pl USING (plan_id)
      WHERE pl.plan_name = 'Day Pass') d USING (city_id, observed_date)
ORDER BY a.city_id, a.observed_date;
