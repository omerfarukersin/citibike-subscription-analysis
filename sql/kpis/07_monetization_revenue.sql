-- KPI category: MONETIZATION (NYC)
-- Revenue mix (month-to-date, preliminary and unaudited per the reports), membership sales per member,
-- rider revenue per trip, and list-price MRR = annual members x annual list price / 12.
-- The list price is the latest observation on or before the FIRST day of the month. Snapshots are not change
-- dates, so the price is carried forward between observations (days_since_price_observation shows how far).
-- List-price MRR is an upper bound: some members pay discounted rates (employer, Reduced Fare, Lyft Pink).
-- membership_sales_per_member = one month's membership revenue / all members (cash collected that month,
-- not a per-member monthly fee). rider_revenue = all revenue paid by riders: every category except Tax and
-- Sponsorship, so it INCLUDES Memberships and Lyft Pink (it is not usage/ride fees only).
-- rider_revenue_per_trip = rider_revenue / all trips (members and casual riders).
-- Tax is sales tax collected from riders and passed on to the government, so it is not Citi Bike's revenue:
-- the revenue mix leaves it out (shares are of revenue before tax) and revenue_before_tax = TOTAL - Tax.
-- total_revenue keeps the report's TOTAL, which includes the tax collected.
-- Feb and May 2026 reports were not published: their revenue is calculated from the neighbouring reports'
-- year-to-date columns (basis = 'derived_from_ytd'), not estimated. Member counts for those months stay NULL,
-- so the per-member and per-trip ratios stay NULL too.
-- Source tables: revenue, monthly_operations, plan_price
CREATE OR REPLACE VIEW kpi_revenue_mix AS
SELECT year_month, category, amount_mtd_usd, basis,
       amount_mtd_usd / sum(amount_mtd_usd) OVER (PARTITION BY year_month) AS share_of_total
FROM revenue
WHERE category NOT IN ('TOTAL', 'Tax');

CREATE OR REPLACE VIEW kpi_monetization_monthly AS
WITH m AS (
    SELECT o.year_month, o.total_annual_members, o.trips_total,
           max(r.amount_mtd_usd) FILTER (WHERE r.category = 'Memberships') AS membership_revenue,
           max(r.amount_mtd_usd) FILTER (WHERE r.category = 'Lyft Pink')   AS lyft_pink_revenue,
           max(r.amount_mtd_usd) FILTER (WHERE r.category = 'TOTAL')       AS total_revenue,
           max(r.amount_mtd_usd) FILTER (WHERE r.category = 'TOTAL')
             - coalesce(max(r.amount_mtd_usd) FILTER (WHERE r.category = 'Tax'), 0) AS revenue_before_tax,
           sum(r.amount_mtd_usd) FILTER (WHERE r.category NOT IN ('TOTAL', 'Tax', 'Sponsorship')) AS rider_revenue,
           max(r.basis)                                                    AS revenue_basis,
           strptime(o.year_month || '-01', '%Y-%m-%d')::DATE              AS month_start
    FROM monthly_operations o
    LEFT JOIN revenue r USING (city_id, year_month)
    WHERE o.city_id = 'NYC'
    GROUP BY ALL
)
SELECT m.year_month, m.total_annual_members, m.total_revenue, m.revenue_before_tax, m.revenue_basis, m.membership_revenue, m.lyft_pink_revenue,
       m.membership_revenue / m.total_annual_members AS membership_sales_per_member,
       m.rider_revenue,
       m.rider_revenue / m.trips_total                AS rider_revenue_per_trip,
       p.price_usd                                   AS annual_list_price,
       p.observed_date                               AS price_observed_date,
       date_diff('day', p.observed_date, m.month_start) AS days_since_price_observation,
       m.total_annual_members * p.price_usd / 12     AS list_price_mrr,
       m.total_annual_members * p.price_usd          AS list_price_arr
FROM m
ASOF LEFT JOIN (SELECT observed_date, price_usd FROM plan_price WHERE plan_id = 'NYC_ANNUAL') p
     ON m.month_start >= p.observed_date
ORDER BY m.year_month;
