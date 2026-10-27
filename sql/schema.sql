-- Citi Bike subscription analysis: ERD as SQL (DuckDB)
-- Window: 2023-07-01 .. 2026-06-30. Cities: NYC (Citi Bike), CHI (Chicago Divvy).

-- ───────────── Dimensions ─────────────
CREATE TABLE city (
    city_id            VARCHAR PRIMARY KEY,          -- 'NYC', 'CHI'
    city_name          VARCHAR NOT NULL,
    system_name        VARCHAR NOT NULL,             -- Citi Bike, Divvy
    operator           VARCHAR NOT NULL,
    weather_station_id VARCHAR NOT NULL              -- NOAA GHCN-Daily station
);

CREATE TABLE calendar_date (
    date        DATE PRIMARY KEY,
    year        INTEGER NOT NULL,
    month       INTEGER NOT NULL,
    year_month  VARCHAR NOT NULL,                    -- 'YYYY-MM'
    day_of_week VARCHAR NOT NULL,
    is_weekend  BOOLEAN NOT NULL,
    is_holiday  BOOLEAN NOT NULL,                    -- US federal holiday
    season      VARCHAR NOT NULL                     -- Winter/Spring/Summer/Autumn
);

CREATE TABLE rider_type (
    rider_type  VARCHAR PRIMARY KEY,                 -- 'member', 'casual'
    description VARCHAR NOT NULL
);

CREATE TABLE plan (
    plan_id         VARCHAR PRIMARY KEY,             -- e.g. 'NYC_ANNUAL'
    city_id         VARCHAR NOT NULL REFERENCES city(city_id),
    plan_name       VARCHAR NOT NULL,
    billing_cycle   VARCHAR NOT NULL,
    is_subscription BOOLEAN NOT NULL,
    rider_type      VARCHAR REFERENCES rider_type(rider_type)   -- how its trips are counted
);

CREATE TABLE station (
    station_key  VARCHAR PRIMARY KEY,                -- city_id || ':' || station_id
    city_id      VARCHAR NOT NULL REFERENCES city(city_id),
    station_id   VARCHAR NOT NULL,
    station_name VARCHAR,
    lat          DOUBLE,
    lng          DOUBLE
);

-- ───────────── Facts ─────────────
CREATE TABLE plan_price (
    plan_id        VARCHAR NOT NULL REFERENCES plan(plan_id),
    observed_date  DATE NOT NULL,                    -- snapshot date or official effective date
    price_usd      DECIMAL(8,2) NOT NULL,
    per_minute_usd DECIMAL(6,2),
    source_url     VARCHAR NOT NULL,
    PRIMARY KEY (plan_id, observed_date)
);

CREATE TABLE weather_daily (
    city_id       VARCHAR NOT NULL REFERENCES city(city_id),
    date          DATE NOT NULL REFERENCES calendar_date(date),
    tmax_c        DOUBLE,
    tmin_c        DOUBLE,
    precip_mm     DOUBLE,
    snow_mm       DOUBLE,
    snow_depth_mm DOUBLE,
    wind_ms       DOUBLE,
    PRIMARY KEY (city_id, date)
);

CREATE TABLE daily_ridership (                       -- trips by end date, 1-120 min (BTS counting rule)
    city_id      VARCHAR NOT NULL REFERENCES city(city_id),
    date         DATE NOT NULL REFERENCES calendar_date(date),
    rider_type   VARCHAR NOT NULL REFERENCES rider_type(rider_type),
    trips        BIGINT NOT NULL,
    trip_minutes DOUBLE NOT NULL,
    source       VARCHAR NOT NULL,                   -- NYC: BTS; CHI: Divvy trip files (BTS doubles Jan 2026)
    PRIMARY KEY (city_id, date, rider_type)
);

CREATE TABLE qa_bts_daily (                          -- BTS figures kept only for cross-checks
    city_id      VARCHAR NOT NULL REFERENCES city(city_id),
    date         DATE NOT NULL REFERENCES calendar_date(date),
    rider_type   VARCHAR NOT NULL REFERENCES rider_type(rider_type),
    trips        BIGINT NOT NULL,
    trip_minutes DOUBLE NOT NULL,
    PRIMARY KEY (city_id, date, rider_type)
);

CREATE TABLE qa_bts_jersey_city_daily (              -- BTS Citi Bike Jersey City system, cross-check only
    date         DATE NOT NULL REFERENCES calendar_date(date),
    rider_type   VARCHAR NOT NULL REFERENCES rider_type(rider_type),
    trips        BIGINT NOT NULL,
    PRIMARY KEY (date, rider_type)
);

CREATE TABLE monthly_operations (                    -- source: Citi Bike monthly operating reports (NYC)
    city_id                     VARCHAR NOT NULL REFERENCES city(city_id),
    year_month                  VARCHAR NOT NULL,
    report_published            BOOLEAN NOT NULL,
    total_annual_members        INTEGER,
    report_mentions_jersey_city BOOLEAN,             -- sentence present until Feb 2025; NOT a scope flag
    trips_include_jersey_city   BOOLEAN,             -- from Mar 2025 (tested in qa_report_vs_bts_jc)
    annual_signups_or_renewals  INTEGER,             -- new + renewed combined (do not derive churn)
    trips_total                 BIGINT,
    trips_member                BIGINT,
    trips_casual                BIGINT,
    avg_trip_minutes            DOUBLE,
    active_stations             INTEGER,
    avg_fleet                   DOUBLE,
    source_file                 VARCHAR,
    PRIMARY KEY (city_id, year_month)
);

CREATE TABLE support_contacts (                      -- one row per month x channel
    city_id                VARCHAR NOT NULL REFERENCES city(city_id),
    year_month             VARCHAR NOT NULL,
    channel                VARCHAR NOT NULL,         -- 'phone', 'email/web form'
    contacts               INTEGER NOT NULL,
    avg_handle_minutes     DOUBLE,                   -- phone only
    source_file            VARCHAR NOT NULL,
    PRIMARY KEY (city_id, year_month, channel),
    FOREIGN KEY (city_id, year_month) REFERENCES monthly_operations(city_id, year_month)
);

CREATE TABLE pass_sales (
    plan_id     VARCHAR NOT NULL REFERENCES plan(plan_id),
    year_month  VARCHAR NOT NULL,
    quantity    INTEGER NOT NULL,
    source_file VARCHAR NOT NULL,
    PRIMARY KEY (plan_id, year_month)
);

CREATE TABLE revenue (
    city_id        VARCHAR NOT NULL REFERENCES city(city_id),
    year_month     VARCHAR NOT NULL,
    category       VARCHAR NOT NULL,
    amount_mtd_usd DECIMAL(14,2),                    -- NULL where the report shows '-'
    amount_ytd_usd DECIMAL(14,2),                    -- year-to-date column of the same report
    basis          VARCHAR NOT NULL,                 -- 'reported', or 'derived_from_ytd' for unpublished months
    source_file    VARCHAR NOT NULL,                 -- for derived rows: the two reports used
    PRIMARY KEY (city_id, year_month, category),
    FOREIGN KEY (city_id, year_month) REFERENCES monthly_operations(city_id, year_month)
);

CREATE TABLE trip_sample (                           -- source: system trip files, 4 sample months per city
    city_id           VARCHAR NOT NULL REFERENCES city(city_id),
    ride_id           VARCHAR NOT NULL,
    rider_type        VARCHAR NOT NULL REFERENCES rider_type(rider_type),
    rideable_type     VARCHAR,
    started_at        TIMESTAMP NOT NULL,
    ended_at          TIMESTAMP NOT NULL,
    date              DATE NOT NULL REFERENCES calendar_date(date),
    duration_min      DOUBLE NOT NULL,
    start_station_key VARCHAR REFERENCES station(station_key),
    end_station_key   VARCHAR REFERENCES station(station_key),
    is_valid          BOOLEAN NOT NULL,              -- BTS rule: 1-120 min; NYC also needs both stations
    PRIMARY KEY (city_id, ride_id)
);

-- ───────────── NYC DOT Citywide Mobility Survey 2024 ─────────────
CREATE TABLE survey_code (                           -- value labels from the official data dictionary
    variable VARCHAR NOT NULL,
    code     INTEGER NOT NULL,
    label    VARCHAR NOT NULL,
    PRIMARY KEY (variable, code)
);

CREATE TABLE survey_respondent (
    person_id      BIGINT PRIMARY KEY,
    hh_id          BIGINT NOT NULL,
    age_code       INTEGER,
    gender_code    INTEGER,
    employment_code INTEGER,
    citi_bike_freq_code INTEGER,
    citi_bike_type_code INTEGER,
    person_weight  DOUBLE                            -- citywide weight (adults 18+)
);

CREATE TABLE survey_plan_held (                      -- Citi Bike users only
    person_id   BIGINT PRIMARY KEY REFERENCES survey_respondent(person_id),
    access_code INTEGER NOT NULL,
    plan_id     VARCHAR REFERENCES plan(plan_id)     -- NULL where no matching plan (e.g. employer discount)
);

CREATE TABLE survey_non_use_reason (                 -- one row per reason selected
    person_id   BIGINT NOT NULL REFERENCES survey_respondent(person_id),
    reason_code INTEGER NOT NULL,                    -- 1..8 = no_bike_share_N
    PRIMARY KEY (person_id, reason_code)
);
