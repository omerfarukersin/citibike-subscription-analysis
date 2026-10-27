# QA audit: Citi Bike vs Divvy pipeline

Audit date: 2026-10-13. A separate, read-only review pass run after the pipeline was built (carried out with an AI coding assistant acting as reviewer, then checked by hand). No pipeline code or data was changed during the audit.

> **Status after the audit.** This file is kept as written on the audit date. Fixes applied afterwards include: survey universe reworded (cyclists only) in findings.md and the KPI views; BTS Jersey City series added with the `qa_report_vs_bts_jc` check; the price carry-forward is stated in `07_monetization_revenue.sql`; `rows_with_nulls` renamed to `rows_flagged`; the "report not published" branch in `extract_reports.py` now fires. The staging column `members_include_jersey_city` was renamed `report_mentions_jersey_city`, matching the schema column, and the YTD cross-check now treats a '-' month-to-date cell as 0 (it previously left 5 rows of `qa/revenue_ytd_checks.csv` empty). `PLAN.md` mentioned below was an internal planning note and is not part of this repository.
Method: `citibike.duckdb` opened read-only. I re-read every raw source myself (pypdf, regex-stripped HTML, pandas on raw CSV and XLSX) and compared it with the DB. I also re-queried the BTS public API once to test a claim that the saved raw files cannot reproduce.

**Overall verdict: PASS WITH FIXES.** Source fidelity is very good: I found no extraction error in any report, price, weather or survey value checked. One FAIL is about interpretation: the survey universe is described wrongly in findings.md and in two KPI views. There are also several WARNs about labelling, undocumented checks and derived values.

## 1. Source fidelity: monthly reports (most important)

Random sample: `random.seed(20261013)`, `random.sample(published_months, 5)` gave **2024-01, 2024-07, 2025-03, 2025-12, 2026-01**. I compared every field in `monthly_operations`, `support_contacts`, `pass_sales` and `revenue` (all 10 categories, MTD column) by hand against the pypdf text.

| Check | Result | Evidence |
|---|---|---|
| monthly_operations, 5 months x 10 fields | PASS | e.g. 2024-01: PDF "Total annual membership stands at 126,629", "4,505 annual members … signed up or renewed", "There were 1,881,808 trips", "recording 1,673,277 trips, compared to 208,531", "2,203 active stations", "average bike fleet … 37,278.0", "10 minutes 49 seconds" -> DB 126629 / 4505 / 1881808 / 1673277 / 208531 / 2203 / 37278 / 10.82. 2025-12: 134,579 / 4,159 / 2,140,234 / 1,910,546 / 229,688 / 2,328 / 32,000 / 10m4s=10.07, all equal. 2024-07, 2025-03 and 2026-01 also match. |
| support_contacts, 5 months | PASS | 2024-07: "17,488 total customer service calls", "7 minutes 42 seconds", "3,565 emails and web forms" -> 17488 / 7.70 / 3565. 2026-01: 3,389 / 18m35s=18.58 / 1,034, all equal. |
| pass_sales, 5 months | PASS | 2025-03: "6,379 annual passes, 93,300 single-trip passes and 8,681 single-day passes" -> 6379/93300/8681. 2024-01 includes "0 three-day passes" -> 0. |
| revenue, 5 months x 10 categories (MTD) | PASS | 2024-07 MTD: Membership 3,502,606.88; Casual 7,565,899.95; Overages "-" -> NULL; Ebike Surch. 9,401,100.44; Classic Ref. -292,650.70; Ebike Ref. -19,851.86; Tax 1,794,390.85; Sponsorship 152,203.60; Lyft Pink 1,941,041.60; TOTAL 24,044,740.76. All match, and so does the MTD column (not YTD) for the other 4 months, including the `$-107,462.79` sign format (2025-12). |
| Full scan, all 34 published months | PASS | Every non-NULL value in the 4 tables appears verbatim in its PDF (0 misses). NULLs: Overages in 17 months and Ebike Refunds in 2024-05/06. The PDF prints "-" (a dash) in those cells, e.g. 2024-05 "Ebike Refunds & Discounts - -$143,173.86", so these are genuine NULLs and nothing was filled. |
| member + casual = total trips | PASS | 0 months with a difference. |
| Revenue: categories sum = TOTAL (random `seed 20261013` -> 2023-10, 2024-10, 2025-09; then all months) | PASS | Differences are 0.00 in all 34 months. |
| Unpublished months 2026-02, 2026-05 | PASS | All fields NULL, `report_published = false`. Not filled. |
| 2024-01 emails/web forms = 0 | WARN | The PDF literally says "0 emails and web forms". This is the only zero in 34 months and is most likely a reporting gap, but `kpi_support_monthly` treats it as a real 0. |
| `members_include_jersey_city` flag | WARN | The flag is TRUE when the sentence "including memberships purchased with Jersey City billing zip codes" is present, which is the case up to 2025-02. It is FALSE from 2025-03 only because the sentence is gone. The PDFs do not say Jersey City members were excluded, but the column name suggests that they were. The data dictionary gives no description. |
| `qa/report_extraction_issues.csv` | WARN (minor) | The "report not published" branch never fires: `source_file` is NaN, not None. Unpublished months show up as 5 "… not found" rows instead. |

## 2. Prices (`plan_price`, 27 rows)

| Check | Result | Evidence |
|---|---|---|
| All 27 rows vs tag-stripped HTML | PASS | NYC 2023-08-13 "$4.49 for 30 mins $19/day $205/year $199/year"; 2024-07-28 "$4.79 … $19/day $219.99/year $199/year"; live 2026-10-13 "$4.99 … $25/day $239/year $199/year". CHI 2024-08-20 "$1 + $0.18/min $18.10/day $143.90/year $199/year"; 2026-01-05 "$1 + $0.19/min $18.10/day $143.90/year* ($99/year …)"; live "$1 + $0.20/min $19.90/day $143.90/year* ($99/year …)". The notice says "Increases to $239/year (effective Jan 28, 2026)". All 27 values, per-minute rates and dates match. |
| Independent sanity check | PASS | The CMS 2024 survey dictionary lists "$219.99/year", "$4.79/trip" and "$19/day". These match the 2024-07 snapshot. |

## 3. Weather (`weather_daily`)

| Check | Result | Evidence (`random.seed(7141)`, 5 rows) |
|---|---|---|
| 5 random rows vs NOAA raw | PASS | NYC 2023-07-06 raw TMAX 322, TMIN 239, PRCP 0, AWND 6 -> 32.2 / 23.9 / 0.0 / 0.6. NYC 2023-11-07 178/117/15/23 -> 17.8/11.7/1.5/2.3. CHI 2024-06-18 344/256/0/69 -> 34.4/25.6/0/6.9. NYC 2024-04-30 189/111/8/33 -> 18.9/11.1/0.8/3.3. CHI 2025-05-21 111/89/15/44 -> 11.1/8.9/1.5/4.4. SNOW and SNWD are kept in mm, correctly. |
| Blizzard 2026-02-23 | PASS | Raw PRCP 269, SNOW 277, SNWD 356 -> 26.9 mm / 277 mm / 356 mm, which matches PLAN's "27.7 cm". |

## 4. Survey (CMS 2024)

| Check | Result | Evidence |
|---|---|---|
| `kpi_survey_plan_held` weighted shares (raw CSV, `person_weight_citywide`, excl. 995) | PASS | Recomputed: code 1 = 0.462526, 2 = 0.176007, 3 = 0.137370, 4 = 0.053659, 5 = 0.061100, 6 = 0.015431, 7 = 0.058605, 997 = 0.035301. All identical to the view. n = 468. |
| `kpi_survey_frequency`, `kpi_non_use_reasons` | PASS (numbers) | Frequency 0.4948 / 0.1936 / 0.1680 / 0.0569 / 0.0536 / 0.0332. Reasons 2 = 0.3532, 3 = 0.2785, 4 = 0.5173, etc. All identical. |
| Labels vs data dictionary | PASS | `survey_code` labels for citi_bike_pay, citi_bike_freq and no_bike_share_1..8 match the "Column Information" sheet word for word. |
| **Survey universe** | **FAIL** | Questionnaire 9.15: CITI_BIKE_FREQ is asked only "If bike_freq > never". The data confirm this: every respondent with bike_freq 6/995/996 has citi_bike_freq = 995. Respondents who answered represent only **34.3% of weighted adults**. Yet `05_engagement_survey_frequency.sql` says "among adults", and findings.md says "49.5% never used Citi Bike (adults)" and "19.4% **of adults** … lapsed". The correct base is **adults who ride a bicycle**. Of all adults, only 16.9% are confirmed never-users. The non-use reasons, e.g. "too expensive 35%", are likewise among cyclists who don't use Citi Bike, not among all non-users. |
| Code 997 "Other" classed as non-subscription | WARN | `coalesce(pl.is_subscription, false)` gives "Other" (3.5%) a value the source does not provide. It should be NULL or "unknown". |

## 5. Cross-checks (`qa/*.csv`)

| Check | Result | Evidence and explanation |
|---|---|---|
| Report vs BTS (NYC) | PASS | Jul 2023 – Feb 2025: BTS is 0.07–0.28% below the report. Mar 2025 – Jun 2026: 2.47–2.77% below, a step change. All differences are below 5%. |
| PLAN/findings explanation of the step (JC/Hoboken from Mar 2025) | WARN | **Correct, but not reproducible from the repo.** I queried the BTS API for "CitiBike (Jersey City, NJ)". From Mar 2025, (BTS NYC + BTS JC)/report − 1 is between −0.37% and −0.66%, so findings' "within 0.7%" holds. Before Mar 2025 the same sum is +2.0 to +2.6% above the report, which confirms the scope change. However, the JC series is not saved in `data/raw/bts`, has no SQL/QA view and is not in source_log. PLAN says "verified against BTS" with no traceable evidence. |
| Sample vs BTS | PASS | NYC 8 rows within ±0.053%. CHI within ±0.02%, except **CHI 2026-01, −50.0%** (member 109,377 vs BTS 218,738). This is explained by BTS double-counting, confirmed in `qa_chi_files_vs_bts`. |
| Chicago files vs BTS | WARN (wording) | 2026-01: BTS 266,184 vs files 133,107 = **+99.98%**. PLAN says "exactly +100%". The other 35 months: max abs 0.0153% (2026-03), 0.0146% (2023-07). PLAN says "within 0.01%", which is not true. The explanation (BTS double count, so the Divvy files are used) is correct. |
| Completeness | WARN (labelling) | The column is called `rows_with_nulls`, but for daily_ridership it counts `trips = 0` (the 2 NYC rows are 2026-02-23) and for monthly_operations it counts unpublished months. The label is misleading. |
| 2026-02-23 zero trips "real, not missing" | WARN | BTS reports 0 for every NYC row that day, and NOAA shows 277 mm of snow. That makes "real" plausible, but no independent source confirms a service suspension: the Feb 2026 report is unpublished and no trip file was downloaded. A BTS outage would look the same. The day also enters the H1 baselines. |
| Trip quality | PASS | NYC 99.46% valid. CHI 96.59% valid (no station requirement, which is documented). 22% of CHI trips have no start station, which is normal for Divvy's dockless e-bikes. |

## 6. KPI logic (`sql/kpis/*.sql`) against standard subscription KPI definitions

| KPI / view | Result | Finding |
|---|---|---|
| 01 Acquisition sign-ups | WARN | The "signups" figure includes renewals. This is labelled and the standard definition is new customers only, so it is acceptable if the wording is always "sign-ups or renewals". YoY uses lag(12) over 36 rows that include the NULL months, so offsets are correct. |
| 03/13 Engagement, member share | PASS | Calendar-month sums of daily BTS/Divvy data, no double counting. NYC = BTS NYC only. |
| 04 Trips per member | WARN | `trips_member` includes JC/Hoboken trips from Mar 2025, while the membership definition change is unknown. The ratio may break at Mar 2025. findings.md mentions this. |
| 06 Retention, net growth | WARN | Correctly does not compute churn. But `net_growth_yoy` for 2025-03..2026-02 compares a count described as "including JC billing zips" with a count that has no such wording. findings quotes "+5.6% (Sep 2025)" without this caveat. Net growth is not the guide's retention rate and should be called "net membership growth", which it is. |
| 05 "Lapsed users = retention proxy" | FAIL | Same universe error as section 4. |
| 07 `membership_revenue_per_member` | WARN | Monthly cash from annual-membership sales (new + renewals, paid up front) divided by the stock of all members. This is not ARPU and is easy to misread. It also excludes Lyft Pink revenue, whose holders are probably in the member count. |
| 07 `revenue_per_trip` | WARN | The numerator TOTAL includes Sponsorship (lumpy, e.g. $4.25M in Jan 2026, $8.6M in May 2024) and Tax. It is not a usage-revenue metric. Exclude both or rename it. |
| 07 List-price MRR/ARR | WARN | The ASOF join carries prices forward: $205 (seen 2023-08-13) is applied to every month through 2024-06, and $219.99 (seen 2024-07-28) from 2024-07 to 2025-12. The real change dates are unknown, so 11+17 monthly prices are assumed rather than observed. Jan 2026 gets $239 for the whole month although it took effect on 28 Jan. The price is also applied to Lyft Pink, employer and reduced-fare ($5/month) members: per the survey, only about 40% of subscribers pay full price. The "upper bound" caveat exists, but the carry-forward should also be stated. 2023-07 is correctly NULL. |
| 07 Revenue mix | PASS | Shares divide by the sum of categories, which equals TOTAL. |
| 08 Break-even | PASS | Only same-snapshot pairs are used. Values 7.23–7.95 (CHI) and 9.56–11.58 (NYC) match findings. |
| 09 Support | PASS / WARN | Recomputed 2024-01: 8,738 / 1,881,808 × 100 = 0.464, and the PDF says "0.46". The denominator includes JC from Mar 2025, so this needs a scope note. The 2024-01 zero emails issue is listed in section 1. |
| 11 H1 weather | WARN (minor) | The method is sound, with associations worded correctly. `h1_temperature_effect` uses raw average trips, not the baseline ratio, so it is confounded with season. findings says casual riders fall "by 5–8 pp" more "in every weather condition", but light rain gives 4.0 pp (NYC) and 1.8 pp (CHI). |
| 12 H2, 13 H3, 14 H4 | PASS | All findings numbers reproduce: ratios 0.39–0.57 / 0.15–0.28 / 0.29–0.36 / 0.10–0.13; member share 81.0/81.8/82.6 vs 64.7/64.0/64.9; e-bike 77.5/70.5/71.2/65.7%. The H4 comment says "both stations known", but CHI has no station requirement (comment only). |
| Standard KPIs not computable | Note | DAU/MAU, churn, cohorts, CAC and NPS/CSAT need customer-level data, which the public sources do not have. The documented proxies are acceptable. |

## 7. Source validation checklist per source (`docs/source_log.csv`)

| Source | Publisher | Real/anon/synthetic stated | Period | Independent sanity check | URL + access date | Verdict |
|---|---|---|---|---|---|---|
| Citi Bike trip history | Y | Y | Y | Y (vs BTS, ±0.05%) | Y | PASS |
| Divvy trip history | Y | Y | Y | Y (vs BTS, ±0.02%) | Y | PASS |
| Citi Bike monthly reports | Y | Y (preliminary/unaudited) | Y | Y (vs BTS) | Y (+ per-file URLs in report_index.csv) | PASS |
| Citi Bike pricing (live + Wayback) | Y | Y | Y | Y (survey dictionary prices) | Y | PASS |
| Citi Bike 2026 price notice | Y | Y | Y | Y (live pricing page $239) | Y | PASS |
| Divvy pricing (live + Wayback) | Y | Y | Y | **N**: compared only with Divvy's own pages | Y | WARN |
| BTS daily ridership | Y | Y | Y | Y (vs both trip-file sets) | Y | PASS |
| NOAA GHCN-Daily | Y | Y | Y | **N**: no independent check recorded | Y | WARN |
| NYC CMS 2024 survey | Y | Y | Partly: "2024 survey", no fieldwork dates | Y (prices match pricing snapshot) | Y | WARN |
| BTS "CitiBike (Jersey City, NJ)" series | used in findings.md | – | – | – | **not logged** | FAIL |

## 8. Untraceable or filled values

| Item | Result |
|---|---|
| Invented, typed or simulated data in tables | PASS: none found. All report, price, weather and survey values trace to raw files. |
| findings.md "NYC + Jersey City in BTS matches the report within 0.7%" | WARN: true (I reproduced it at max 0.66%), but no file, query or source-log entry in the repo supports it. |
| PLAN "exactly +100%", "within 0.01%" | WARN: inaccurate. The real values are +99.98% and max 0.0153%. |
| Carried-forward list prices in `kpi_monetization_monthly` and `nyc_monthly_kpis.csv` | WARN: these are derived assumptions, not observations (section 6). |
| `is_subscription = false` for survey "Other" | WARN: a classification the source does not provide. |
| 2024-01 emails = 0 | WARN: reported by the source but likely not a real zero. |

## Required fixes (ranked by severity)

1. **(FAIL, high)** Correct the survey universe everywhere. `citi_bike_freq`, `citi_bike_pay` and `no_bike_share_*` cover only adults who ride a bicycle (about 34% of weighted adults). Reword findings.md ("49.5% never used", "19.4% of adults lapsed", non-use reasons), `05_engagement_survey_frequency.sql` and `10_satisfaction_non_use_reasons.sql`. Do not present "lapsed cyclists" as a retention rate for adults.
2. **(FAIL, medium)** Add the BTS Jersey City series to `data/raw/bts`, `docs/source_log.csv` and a QA view (report vs BTS NYC + JC). The Mar 2025 scope-change claim then becomes reproducible. Until then, change "verified" in PLAN.md to "inferred".
3. **(WARN, medium)** In `kpi_monetization_monthly`, state the price carry-forward, or show `list_price_mrr` only for months with a snapshot or notice. Rename or redefine `revenue_per_trip` to exclude Sponsorship and Tax, and `membership_revenue_per_member` (it is cash per member, not ARPU).
4. **(WARN, medium)** Rename `members_include_jersey_city` (e.g. `report_mentions_jc_billing_zips`) and document it. Flag YoY net growth and trips-per-member across Mar 2025 as definition-break months.
5. **(WARN, low)** Fix PLAN.md wording: +99.98% (not "exactly +100%") and "within 0.02%" (not 0.01%). Fix findings' "5–8 pp in every condition", which holds for moderate/heavy rain and snow but not light rain.
6. **(WARN, low)** Treat the 2024-01 emails value (0) as suspect or NULL in the satisfaction trend, with a note. Describe 2026-02-23 as "BTS reports zero trips; consistent with a 27.7 cm snowfall", not as confirmed.
7. **(WARN, low)** Add independent sanity checks for NOAA (e.g. a second station or a published monthly climate summary) and for Divvy prices (a news or press-release figure). Add the survey fieldwork period to source_log.
8. **(WARN, low)** Rename the `qa_completeness.rows_with_nulls` column. Fix the unreachable "report not published" branch in `extract_reports.py`. Set the survey "Other" access method's `is_subscription` to NULL. Fix the H4 comment.
