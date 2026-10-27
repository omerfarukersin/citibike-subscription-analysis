# Findings: Citi Bike (NYC) vs Divvy (Chicago), Jul 2023 – Jun 2026

All figures come from the views in `sql/kpis/` and are exported to `data/marts/`. Weather and city results are **associations, not causes**.

## Hypotheses

### H1: Casual riders are more weather-sensitive than members → **supported**
Trips are compared with a normal day for the same city, rider type, month and weekday/weekend type (`h1_*` views). The table compares the average normal-day ratio on rain or snow days with the same ratio on dry days (or on winter days without snow). Against the normal-day baseline itself, heavy rain is −40% / −33% for NYC casual / member and −31% / −25% in Chicago.

| Change vs a dry day | NYC member | NYC casual | Chicago member | Chicago casual |
|---|---|---|---|---|
| Moderate rain (5–20 mm) | −22% | −29% | −20% | −26% |
| Heavy rain (20+ mm) | −37% | −44% | −29% | −35% |
| Snow day vs no-snow winter day | −34% | −42% | −14% | −22% |

- In both cities, in moderate or heavy rain and on snow days, **casual trips fall further than member trips**, by 5–8 percentage points. In light rain the gap is small (4 points in NYC, 2 in Chicago).
- Members are the stable base. This fits the subscription logic: a member has already paid, so the marginal cost of a ride is close to zero.
- Chicago riders are less affected by snow than New Yorkers. One possible reason is that Chicago has many more snow days (55 vs 29 winter days in the window), so riders and the operator are more used to it. That explanation is a guess and is not tested here.

### H2: The winter drop is deeper in Chicago, and members hold up better → **supported**
Winter-to-summer ratio = average daily trips in Dec–Feb ÷ Jun–Aug (`h2_seasonality`).

| | NYC member | NYC casual | Chicago member | Chicago casual |
|---|---|---|---|---|
| Range over 3 winters | 0.39–0.57 | 0.15–0.28 | 0.29–0.36 | 0.10–0.13 |

- **Chicago's casual ridership falls to about 10–13% of its summer level**, against 15–28% in NYC.
- Members keep roughly 3× more of their summer riding than casual users in Chicago, and about 2× more in NYC.
- In NYC, the coldest winter (2025-26, average Dec–Feb max 3.3 °C, including the 23 Feb 2026 blizzard with zero trips) had the lowest ratios. Chicago's coldest winter was 2024-25 (1.2 °C, vs 1.6 °C in 2025-26).

### H3: Member share differs between cities → **supported; price alone doesn't explain it**
| Ride year (Jul–Jun) | NYC member share | Chicago member share |
|---|---|---|
| 2023-24 | 81.0% | 64.7% |
| 2024-25 | 81.8% | 64.0% |
| 2025-26 | 82.6% | 64.9% |

- NYC has a **much higher member share even though its annual membership costs more** ($205 → $219.99 → $239, vs Chicago's flat $143.90, or $99 for new members).
- The pricing structures differ in an important way. An NYC single ride is a **flat $4.49–$4.99**, while Chicago charges **$1 + $0.18–0.20 per minute**. A short casual ride is therefore cheaper in Chicago, which may weaken the incentive to subscribe (not tested).
- Break-even: the NYC annual price equals 9.6–11.6 day passes, Chicago's 7.2–8.0. These are associations only. City size, commuting patterns and tourism also differ.

### H4: E-bike use differs by rider type → **supported**
Trip sample (Jul 2025, Oct 2025, Jan 2026, Apr 2026):
- Average e-bike share of trips: **NYC casual 77.5% vs member 70.5%**; Chicago casual 71.2% vs member 65.7%.
- Casual riders lean more on e-bikes, especially in January (NYC casual 82.5%).

## KPIs by category (acquisition, engagement, retention, monetization, satisfaction)

| Category | KPI | Result |
|---|---|---|
| **Acquisition** | Annual sign-ups or renewals (NYC) | Strongly seasonal: about 3,400–4,500 in Jan/Feb vs 18,300–20,600 in Jun–Sep |
| | How Citi Bike users last accessed it (survey 2024, weighted, n = 468 users in the last 12 months) | 44% hold a subscription: full-price annual 17.6%, Lyft Pink annual 13.7%, Reduced Fare 6.1%, employer/school 5.4%, Lyft Pink monthly 1.5%. 46% last paid for a single trip, 6% for a day pass |
| **Engagement** | Member share of trips | NYC 81–83%, Chicago 64–65% |
| | Trips per annual member per month (NYC) | about 12.5–15 in January to about 32 in Sep/Oct |
| | Survey frequency (**adults who cycle at least a few times a year**, about 34% of adults; non-cyclists were not asked) | 49.5% have never used Citi Bike; 14.4% use it at least monthly |
| **Retention** | Net membership growth, year on year (NYC) | from −1.6% (Jul 2024) to +5.6% (Sep 2025); 138,055 members in Jun 2026 vs 127,485 in Jun 2024 |
| | Lapsed users (survey, cyclists) | 19.4% of cyclists used Citi Bike before but not in the last 12 months |
| **Monetization** | Revenue mix (NYC, Jul 2025 – Jun 2026, 12 months; Feb and May 2026 calculated from the year-to-date totals in the neighbouring reports) | E-bike surcharges and fees $101.7M are the largest line; then casual ridership $57.8M, memberships $32.4M, Lyft Pink $18.2M |
| | List-price MRR (members × annual price ÷ 12) | about $2.2M (2023) to $2.7M (Jun 2026). This is an upper bound, because some members pay discounted rates. The price is carried forward between snapshots |
| **Satisfaction** | Support calls per 100 trips (NYC) | 0.57 (2023) → 0.24 (2025) → 0.23 (2026) |
| | Average call handling time | 6.0 min (2023) → 8.4 min (2025) → **15.3 min (2026)**, a warning sign |
| | Reasons for not using (survey, cyclists who don't use Citi Bike) | prefer own bike 52%, **too expensive 35%**, not available nearby 28%, uncomfortable biking in NYC 15% |

## Recommendation figures

Queries and exact definitions: [`sql/analysis/recommendation_checks.sql`](../sql/analysis/recommendation_checks.sql)
(read-only queries on `citibike.duckdb`, not part of the `make` pipeline). The normal-day baseline is the same as in H1.

| Check | Definition (short) | Result |
|---|---|---|
| Revenue per trip by rider type (NYC, Jul 2025 – Jun 2026) | Casual Ridership revenue ÷ BTS casual trips; Memberships + Lyft Pink ÷ BTS member trips; e-bike fees left out of both (not split by rider type) | casual **$7.32** per trip, members **$1.35** per trip (ratio 5.4) |
| Snow on the ground vs snowfall (NYC, Dec 2025 – Feb 2026, every day) | snowfall day: snow > 0; dry day with lying snow: no snowfall, precipitation < 1 mm, snow depth > 0; members + casual together | 13 snowfall days at 55.7% of normal trips, 280,524 trips below normal; 31 dry days with lying snow at 82.4%, 297,713 below normal |
| Warm winter days (both cities, Dec–Feb, 3 winters) | dry (0 mm) day with max temperature ≥ 8 °C above the city's mean max for that calendar month; holidays excluded; simple average of daily ratios | 23 days (19 Chicago, 4 NYC); casual riding **1.77×** a normal day, members **1.43×** (Chicago 1.79× / 1.43×, NYC 1.69× / 1.45×) |

- **Revenue scope caveat.** From March 2025 the report revenue includes Jersey City and Hoboken, as its trip totals do, while the trip counts are BTS New York only. Both per-trip figures are therefore overstated by up to about 2.5%. The roughly fivefold gap between them is unchanged.
- **What this supports:** grow from new riders rather than converting casual riders, because a converted casual rider moves from about $7.32 to about $1.35 per trip in the fees that can be split by rider type. Among cyclists who don't use Citi Bike, 35% say it is too expensive and 28% that it is not available nearby.
- The lying-snow comparison uses a baseline that includes that month's bad-weather days, so lost-trip totals are approximate.

## Data notes that affect interpretation
- **Churn is not measured.** The reports combine new sign-ups and renewals, so net growth is used instead.
- **From Mar 2025, report trip totals include Jersey City and Hoboken.** This is tested in `qa_report_vs_bts_jc`: before Mar 2025, BTS NYC alone matches the report within 0.3%; from Mar 2025, BTS NYC + Jersey City matches within 0.7%. NYC engagement uses BTS (NYC only), so that series is consistent. The report-based ratios (trips per member, calls per 100 trips) carry this scope change.
- **BTS double-counted Chicago in Jan 2026** (+99.98% vs Divvy's files; the other 35 months agree within 0.02%), so Chicago ridership comes from Divvy's own files.
- **The NYC reports for Feb and May 2026 were not published.** Members, sign-ups and support figures are left blank. Revenue is calculated from the year-to-date columns of the neighbouring reports (exact arithmetic, not an estimate; flagged `derived_from_ytd`). It may include small corrections Citi Bike made to earlier months: 295 year-to-date cross-checks over 31 months show Citi Bike's own later revisions (> $1) in 7 of them (`qa/revenue_ytd_checks.csv`). This is why May 2026 shows a sponsorship line of −$384k: the June report's year-to-date sponsorship, less June itself, is $384k below the April report's year-to-date total, which points to a later restatement of an earlier month. Derived revenue for the two months is $4.5M (Feb) and $22.9M (May) before tax.
- **Single-trip pass counts look inconsistent from 2025:** about 1 million a month in summer 2024; in 2025 about 200,000–265,000 in Jan–Feb and May–Sep but 37,000–173,000 in Mar, Apr and Oct–Dec; and Jan and Feb 2025 show the identical figure (199,930). This is probably a counting change or a reporting error, so the series should not be read as a trend.
- **Revenue figures are preliminary and unaudited,** as stated in the reports.
- **Emails/web forms look unreliable from Jul 2023 to Apr 2024:** 1–6 a month in 2023, 0 in Jan 2024, then 119,033 / 118,971 / 118,971 in Feb–Apr 2024 (a repeated value), against roughly 800–3,900 a month later. Do not read a support-contact trend across that period.
- **Unconfirmed values kept as printed:** zero NYC trips on 23 Feb 2026 (consistent with 277 mm of snowfall, but no independent source confirms a service suspension).
- **The survey reports how users paid for their most recent trip,** not a full plan census. Non-cyclists (about 66% of adults) were not asked the Citi Bike questions.
- The NYC call-centre setup changed: an overflow call centre is mentioned in the 2023–24 reports only, so the support figures before and after are not fully comparable.
- **Prices come from snapshots** (Aug 2023, Jul 2024, Oct 2026 for NYC; Aug 2024, Jan 2026, Oct 2026 for Chicago), plus the official notice dating the NYC change to $239 on 28 Jan 2026. Exact dates of the other changes are unknown.
