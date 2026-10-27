# Data dictionary

Generated from `citibike.duckdb` by `src/docs.py`. PK = primary key, FK = foreign key.

## `calendar_date` (1,096 rows)

Source: Generated; US federal holidays from pandas USFederalHolidayCalendar

| Column | Type | Key | Description |
|---|---|---|---|
| `date` | DATE | PK |  |
| `year` | INTEGER |  |  |
| `month` | INTEGER |  |  |
| `year_month` | VARCHAR |  | 'YYYY-MM' |
| `day_of_week` | VARCHAR |  |  |
| `is_weekend` | BOOLEAN |  |  |
| `is_holiday` | BOOLEAN |  | US federal holiday |
| `season` | VARCHAR |  | Winter/Spring/Summer/Autumn |

## `city` (2 rows)

Source: Project configuration (NOAA station IDs from NOAA GHCN-Daily)

| Column | Type | Key | Description |
|---|---|---|---|
| `city_id` | VARCHAR | PK | 'NYC', 'CHI' |
| `city_name` | VARCHAR |  |  |
| `system_name` | VARCHAR |  | Citi Bike, Divvy |
| `operator` | VARCHAR |  |  |
| `weather_station_id` | VARCHAR |  | NOAA GHCN-Daily station |

## `daily_ridership` (4,384 rows)

Source: NYC: BTS Docked Bikeshare Ridership; Chicago: Divvy trip files (all months)

| Column | Type | Key | Description |
|---|---|---|---|
| `city_id` | VARCHAR | PK, FK |  |
| `date` | DATE | PK, FK |  |
| `rider_type` | VARCHAR | PK, FK |  |
| `trips` | BIGINT |  |  |
| `trip_minutes` | DOUBLE |  |  |
| `source` | VARCHAR |  | NYC: BTS; CHI: Divvy trip files (BTS doubles Jan 2026) |

## `monthly_operations` (36 rows)

Source: Citi Bike monthly operating reports (PDF)

| Column | Type | Key | Description |
|---|---|---|---|
| `city_id` | VARCHAR | PK, FK |  |
| `year_month` | VARCHAR | PK |  |
| `report_published` | BOOLEAN |  |  |
| `total_annual_members` | INTEGER |  |  |
| `report_mentions_jersey_city` | BOOLEAN |  | sentence present until Feb 2025; NOT a scope flag |
| `trips_include_jersey_city` | BOOLEAN |  | from Mar 2025 (tested in qa_report_vs_bts_jc) |
| `annual_signups_or_renewals` | INTEGER |  | new + renewed combined (do not derive churn) |
| `trips_total` | BIGINT |  |  |
| `trips_member` | BIGINT |  |  |
| `trips_casual` | BIGINT |  |  |
| `avg_trip_minutes` | DOUBLE |  |  |
| `active_stations` | INTEGER |  |  |
| `avg_fleet` | DOUBLE |  |  |
| `source_file` | VARCHAR |  |  |

## `pass_sales` (122 rows)

Source: Citi Bike monthly operating reports (PDF)

| Column | Type | Key | Description |
|---|---|---|---|
| `plan_id` | VARCHAR | PK, FK |  |
| `year_month` | VARCHAR | PK |  |
| `quantity` | INTEGER |  |  |
| `source_file` | VARCHAR |  |  |

## `plan` (13 rows)

Source: Citi Bike / Divvy pricing pages; survey access options; report pass types

| Column | Type | Key | Description |
|---|---|---|---|
| `plan_id` | VARCHAR | PK | e.g. 'NYC_ANNUAL' |
| `city_id` | VARCHAR | FK |  |
| `plan_name` | VARCHAR |  |  |
| `billing_cycle` | VARCHAR |  |  |
| `is_subscription` | BOOLEAN |  |  |
| `rider_type` | VARCHAR | FK | how its trips are counted |

## `plan_price` (27 rows)

Source: Citi Bike / Divvy pricing pages (Wayback snapshots + live), Citi Bike price-change notice

| Column | Type | Key | Description |
|---|---|---|---|
| `plan_id` | VARCHAR | PK, FK |  |
| `observed_date` | DATE | PK | snapshot date or official effective date |
| `price_usd` | DECIMAL(8,2) |  |  |
| `per_minute_usd` | DECIMAL(6,2) |  |  |
| `source_url` | VARCHAR |  |  |

## `qa_bts_daily` (4,384 rows)

Source: BTS Docked Bikeshare Ridership (cross-check only)

| Column | Type | Key | Description |
|---|---|---|---|
| `city_id` | VARCHAR | PK, FK |  |
| `date` | DATE | PK, FK |  |
| `rider_type` | VARCHAR | PK, FK |  |
| `trips` | BIGINT |  |  |
| `trip_minutes` | DOUBLE |  |  |

## `qa_bts_jersey_city_daily` (2,192 rows)

Source: BTS Docked Bikeshare Ridership, Citi Bike Jersey City (cross-check only)

| Column | Type | Key | Description |
|---|---|---|---|
| `date` | DATE | PK, FK |  |
| `rider_type` | VARCHAR | PK, FK |  |
| `trips` | BIGINT |  |  |

## `revenue` (360 rows)

Source: Citi Bike monthly operating reports (PDF), month-to-date, preliminary/unaudited; Feb and May 2026 calculated from neighbouring reports' year-to-date columns

| Column | Type | Key | Description |
|---|---|---|---|
| `city_id` | VARCHAR | PK, FK |  |
| `year_month` | VARCHAR | PK, FK |  |
| `category` | VARCHAR | PK |  |
| `amount_mtd_usd` | DECIMAL(14,2) |  | NULL where the report shows '-' |
| `amount_ytd_usd` | DECIMAL(14,2) |  | year-to-date column of the same report |
| `basis` | VARCHAR |  | 'reported', or 'derived_from_ytd' for unpublished months |
| `source_file` | VARCHAR |  | for derived rows: the two reports used |

## `rider_type` (2 rows)

Source: Project definition (member = subscription, casual = pay as you go)

| Column | Type | Key | Description |
|---|---|---|---|
| `rider_type` | VARCHAR | PK | 'member', 'casual' |
| `description` | VARCHAR |  |  |

## `station` (4,188 rows)

Source: Trip files (sample months)

| Column | Type | Key | Description |
|---|---|---|---|
| `station_key` | VARCHAR | PK | city_id || ':' || station_id |
| `city_id` | VARCHAR | FK |  |
| `station_id` | VARCHAR |  |  |
| `station_name` | VARCHAR |  |  |
| `lat` | DOUBLE |  |  |
| `lng` | DOUBLE |  |  |

## `support_contacts` (68 rows)

Source: Citi Bike monthly operating reports (PDF)

| Column | Type | Key | Description |
|---|---|---|---|
| `city_id` | VARCHAR | PK, FK |  |
| `year_month` | VARCHAR | PK, FK |  |
| `channel` | VARCHAR | PK | 'phone', 'email/web form' |
| `contacts` | INTEGER |  |  |
| `avg_handle_minutes` | DOUBLE |  | phone only |
| `source_file` | VARCHAR |  |  |

## `survey_code` (80 rows)

Source: NYC DOT Citywide Mobility Survey 2024 data dictionary

| Column | Type | Key | Description |
|---|---|---|---|
| `variable` | VARCHAR | PK |  |
| `code` | INTEGER | PK |  |
| `label` | VARCHAR |  |  |

## `survey_non_use_reason` (1,122 rows)

Source: NYC DOT Citywide Mobility Survey 2024 (no_bike_share_1..8)

| Column | Type | Key | Description |
|---|---|---|---|
| `person_id` | BIGINT | PK, FK |  |
| `reason_code` | INTEGER | PK | 1..8 = no_bike_share_N |

## `survey_plan_held` (468 rows)

Source: NYC DOT Citywide Mobility Survey 2024 (citi_bike_pay)

| Column | Type | Key | Description |
|---|---|---|---|
| `person_id` | BIGINT | PK, FK |  |
| `access_code` | INTEGER |  |  |
| `plan_id` | VARCHAR | FK | NULL where no matching plan (e.g. employer discount) |

## `survey_respondent` (8,569 rows)

Source: NYC DOT Citywide Mobility Survey 2024, Person table

| Column | Type | Key | Description |
|---|---|---|---|
| `person_id` | BIGINT | PK |  |
| `hh_id` | BIGINT |  |  |
| `age_code` | INTEGER |  |  |
| `gender_code` | INTEGER |  |  |
| `employment_code` | INTEGER |  |  |
| `citi_bike_freq_code` | INTEGER |  |  |
| `citi_bike_type_code` | INTEGER |  |  |
| `person_weight` | DOUBLE |  | citywide weight (adults 18+) |

## `trip_sample` (17,392,225 rows)

Source: Citi Bike + Divvy trip files: Jul 2025, Oct 2025, Jan 2026, Apr 2026

| Column | Type | Key | Description |
|---|---|---|---|
| `city_id` | VARCHAR | PK, FK |  |
| `ride_id` | VARCHAR | PK |  |
| `rider_type` | VARCHAR | FK |  |
| `rideable_type` | VARCHAR |  |  |
| `started_at` | TIMESTAMP |  |  |
| `ended_at` | TIMESTAMP |  |  |
| `date` | DATE | FK |  |
| `duration_min` | DOUBLE |  |  |
| `start_station_key` | VARCHAR | FK |  |
| `end_station_key` | VARCHAR | FK |  |
| `is_valid` | BOOLEAN |  | BTS rule: 1-120 min; NYC also needs both stations |

## `weather_daily` (2,192 rows)

Source: NOAA GHCN-Daily (Central Park, O'Hare)

| Column | Type | Key | Description |
|---|---|---|---|
| `city_id` | VARCHAR | PK, FK |  |
| `date` | DATE | PK, FK |  |
| `tmax_c` | DOUBLE |  |  |
| `tmin_c` | DOUBLE |  |  |
| `precip_mm` | DOUBLE |  |  |
| `snow_mm` | DOUBLE |  |  |
| `snow_depth_mm` | DOUBLE |  |  |
| `wind_ms` | DOUBLE |  |  |
