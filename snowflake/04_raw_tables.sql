-- ============================================================
-- NomadHub Snowflake Setup — Step 04: RAW (Bronze) Table DDL
-- ============================================================
-- Column names and types exactly match the CSV structure
-- produced by data/generate_data.py
-- ============================================================

USE ROLE NOMAD_ADMIN;
USE WAREHOUSE NOMAD_WH;
USE DATABASE NOMAD_HUB;
USE SCHEMA RAW;

-- ── 1. countries ──────────────────────────────────────────────────────────────
CREATE OR REPLACE TABLE RAW.COUNTRIES (
    COUNTRY_CODE        VARCHAR(3)      COMMENT 'ISO 3166-1 alpha-2 country code',
    COUNTRY_NAME        VARCHAR(100)    COMMENT 'Full country name',
    REGION              VARCHAR(50)     COMMENT 'Geographic region',
    CURRENCY_CODE       VARCHAR(5)      COMMENT 'ISO 4217 currency code',
    LANGUAGE            VARCHAR(50)     COMMENT 'Primary language',
    TIMEZONE            VARCHAR(20)     COMMENT 'UTC offset string',
    VISA_REQUIRED       BOOLEAN         COMMENT 'Whether most visitors need a visa',
    CREATED_AT          DATE            COMMENT 'Record created date'
)
COMMENT = 'Country & geographic reference data'
;

-- ── 2. airports ───────────────────────────────────────────────────────────────
CREATE OR REPLACE TABLE RAW.AIRPORTS (
    AIRPORT_ID          NUMBER          COMMENT 'Surrogate key',
    IATA_CODE           VARCHAR(3)      COMMENT 'IATA 3-letter airport code',
    AIRPORT_NAME        VARCHAR(200)    COMMENT 'Full official airport name',
    CITY                VARCHAR(100)    COMMENT 'Nearest city',
    COUNTRY_CODE        VARCHAR(3)      COMMENT 'FK → COUNTRIES.COUNTRY_CODE',
    COUNTRY_NAME        VARCHAR(100),
    LATITUDE            FLOAT           COMMENT 'Decimal degrees',
    LONGITUDE           FLOAT           COMMENT 'Decimal degrees',
    ELEVATION_FT        NUMBER          COMMENT 'Elevation above sea level (feet)',
    IS_INTERNATIONAL    BOOLEAN,
    IS_ACTIVE           BOOLEAN,
    CREATED_AT          DATE
)
COMMENT = 'Airport catalog with IATA codes and coordinates'
;

-- ── 3. hotels ─────────────────────────────────────────────────────────────────
CREATE OR REPLACE TABLE RAW.HOTELS (
    HOTEL_ID            NUMBER          COMMENT 'Surrogate key',
    HOTEL_NAME          VARCHAR(200)    COMMENT 'Hotel display name',
    CATEGORY            VARCHAR(30)     COMMENT 'Budget / Economy / Midscale / Upscale / Luxury / Ultra-Luxury',
    STAR_RATING         NUMBER(1)       COMMENT '1–5 star rating',
    COUNTRY_CODE        VARCHAR(3)      COMMENT 'FK → COUNTRIES.COUNTRY_CODE',
    COUNTRY_NAME        VARCHAR(100),
    CITY                VARCHAR(100),
    ADDRESS             VARCHAR(500),
    LATITUDE            FLOAT,
    LONGITUDE           FLOAT,
    TOTAL_ROOMS         NUMBER          COMMENT 'Total room inventory',
    BASE_PRICE_USD      FLOAT           COMMENT 'Lowest published nightly rate in USD',
    HAS_POOL            BOOLEAN,
    HAS_SPA             BOOLEAN,
    HAS_GYM             BOOLEAN,
    HAS_RESTAURANT      BOOLEAN,
    HAS_FREE_WIFI       BOOLEAN,
    PET_FRIENDLY        BOOLEAN,
    IS_ACTIVE           BOOLEAN,
    OPENED_DATE         DATE            COMMENT 'Hotel opening date',
    CREATED_AT          DATE
)
COMMENT = 'Hotel property catalog with amenities and pricing'
;

-- ── 4. users ──────────────────────────────────────────────────────────────────
CREATE OR REPLACE TABLE RAW.USERS (
    USER_ID                 NUMBER          COMMENT 'Surrogate key',
    USERNAME                VARCHAR(100)    COMMENT 'Unique username',
    EMAIL                   VARCHAR(200)    COMMENT 'User email address',
    FIRST_NAME              VARCHAR(100),
    LAST_NAME               VARCHAR(100),
    DATE_OF_BIRTH           DATE,
    GENDER                  VARCHAR(10)     COMMENT 'M / F / Other',
    COUNTRY_CODE            VARCHAR(3)      COMMENT 'FK → COUNTRIES.COUNTRY_CODE',
    CITY                    VARCHAR(100),
    PHONE                   VARCHAR(50),
    LOYALTY_TIER            VARCHAR(20)     COMMENT 'Bronze / Silver / Gold / Platinum',
    LOYALTY_POINTS          NUMBER          COMMENT 'Current loyalty points balance',
    PREFERRED_CABIN         VARCHAR(20)     COMMENT 'Economy / Premium Economy / Business / First',
    PREFERRED_HOTEL_CATEGORY VARCHAR(30),
    NEWSLETTER_SUBSCRIBED   BOOLEAN,
    REGISTRATION_DATE       DATE,
    LAST_LOGIN_DATE         DATE,
    IS_ACTIVE               BOOLEAN,
    CREATED_AT              DATE
)
COMMENT = 'User account profiles and preferences'
;

-- ── 5. flights ────────────────────────────────────────────────────────────────
CREATE OR REPLACE TABLE RAW.FLIGHTS (
    FLIGHT_ID           NUMBER          COMMENT 'Surrogate key',
    BOOKING_REF         VARCHAR(20)     COMMENT 'Human-readable booking reference (NH-Fxxxxxxxxxx)',
    USER_ID             NUMBER          COMMENT 'FK → USERS.USER_ID',
    ORIGIN_IATA         VARCHAR(3)      COMMENT 'Departure airport IATA code',
    DESTINATION_IATA    VARCHAR(3)      COMMENT 'Arrival airport IATA code',
    AIRLINE             VARCHAR(100)    COMMENT 'Airline name',
    FLIGHT_NUMBER       VARCHAR(10)     COMMENT 'Carrier + number (e.g. NH1234)',
    CABIN_CLASS         VARCHAR(20)     COMMENT 'Economy / Premium Economy / Business / First',
    OUTBOUND_DATE       DATE            COMMENT 'Departure date',
    RETURN_DATE         DATE            COMMENT 'Return date (NULL for one-way)',
    IS_ROUND_TRIP       BOOLEAN,
    NUM_PASSENGERS      NUMBER(2)       COMMENT 'Number of travellers on booking',
    BASE_FARE_USD       FLOAT           COMMENT 'Per-person base fare before tax',
    TAXES_USD           FLOAT           COMMENT 'Taxes and fees per person',
    TOTAL_FARE_USD      FLOAT           COMMENT 'Grand total (all passengers, taxes included)',
    BOOKING_DATE        DATE            COMMENT 'Date booking was made',
    BOOKING_STATUS      VARCHAR(20)     COMMENT 'confirmed / cancelled / completed / no_show',
    PAYMENT_METHOD      VARCHAR(30)     COMMENT 'credit_card / debit_card / bank_transfer / digital_wallet / crypto',
    TRAVEL_PURPOSE      VARCHAR(20)     COMMENT 'leisure / business / family / honeymoon / adventure / medical',
    IS_REFUNDABLE       BOOLEAN,
    CHECKED_BAGS        NUMBER(2)       COMMENT 'Number of checked bags',
    CREATED_AT          DATE
)
COMMENT = 'Flight booking fact table — one row per booking'
;

-- ── 6. hotel_bookings ─────────────────────────────────────────────────────────
CREATE OR REPLACE TABLE RAW.HOTEL_BOOKINGS (
    BOOKING_ID          NUMBER          COMMENT 'Surrogate key',
    BOOKING_REF         VARCHAR(20)     COMMENT 'Human-readable reference (NH-Hxxxxxxxxxx)',
    USER_ID             NUMBER          COMMENT 'FK → USERS.USER_ID',
    HOTEL_ID            NUMBER          COMMENT 'FK → HOTELS.HOTEL_ID',
    ROOM_TYPE           VARCHAR(30)     COMMENT 'Standard / Deluxe / Suite / Executive / Presidential',
    CHECK_IN_DATE       DATE,
    CHECK_OUT_DATE      DATE,
    NUM_NIGHTS          NUMBER(3),
    NUM_GUESTS          NUMBER(2),
    NUM_ROOMS           NUMBER(2),
    RATE_PER_NIGHT_USD  FLOAT           COMMENT 'Nightly room rate in USD',
    TOTAL_RATE_USD      FLOAT           COMMENT 'rate × nights × rooms',
    TAXES_USD           FLOAT,
    TOTAL_AMOUNT_USD    FLOAT           COMMENT 'total_rate + taxes',
    BOOKING_DATE        DATE,
    BOOKING_STATUS      VARCHAR(20)     COMMENT 'confirmed / cancelled / completed / no_show',
    PAYMENT_METHOD      VARCHAR(30),
    TRAVEL_PURPOSE      VARCHAR(20),
    IS_REFUNDABLE       BOOLEAN,
    BREAKFAST_INCLUDED  BOOLEAN,
    AIRPORT_TRANSFER    BOOLEAN,
    SPECIAL_REQUESTS    VARCHAR(500),
    CREATED_AT          DATE
)
COMMENT = 'Hotel booking fact table — one row per reservation'
;

-- ── 7. reviews ────────────────────────────────────────────────────────────────
CREATE OR REPLACE TABLE RAW.REVIEWS (
    REVIEW_ID           NUMBER          COMMENT 'Surrogate key',
    USER_ID             NUMBER          COMMENT 'FK → USERS.USER_ID',
    REVIEW_TYPE         VARCHAR(20)     COMMENT 'flight / hotel / destination',
    ENTITY_ID           NUMBER          COMMENT 'ID of the reviewed entity',
    ENTITY_NAME         VARCHAR(200)    COMMENT 'Name of reviewed airline/hotel/destination',
    DESTINATION_CITY    VARCHAR(100),
    RATING              NUMBER(1)       COMMENT '1–5 star rating',
    REVIEW_TITLE        VARCHAR(300),
    REVIEW_TEXT         VARCHAR(5000)   COMMENT 'Free-text review body — used for AI enrichment',
    HELPFUL_VOTES       NUMBER          COMMENT 'Upvotes from other users',
    VERIFIED_BOOKING    BOOLEAN         COMMENT 'TRUE if reviewer has a verified booking',
    REVIEW_DATE         DATE,
    LANGUAGE            VARCHAR(5)      COMMENT 'ISO 639-1 language code',
    CREATED_AT          DATE
)
COMMENT = 'Free-text travel reviews — source for AI LLM enrichment'
;

-- ── Verification ───────────────────────────────────────────────────────────────
SHOW TABLES IN SCHEMA NOMAD_HUB.RAW;
