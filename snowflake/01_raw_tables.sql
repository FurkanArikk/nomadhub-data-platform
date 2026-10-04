-- =====================================================================
-- NomadHub — RAW (Bronze) tables
-- One table per folder in s3://<bucket>/raw/. Every source column is loaded as
-- VARCHAR, exactly as it appears in the file — typing and cleaning happen in dbt
-- staging. Two lineage columns are added on load:
--   _source_file  the S3 key the row came from (METADATA$FILENAME)
--   _loaded_at    when COPY INTO loaded it
-- Column order matches the file headers; generated from them, so do not reorder.
-- Run as LOADER_ROLE (it owns RAW tables; DBT_ROLE reads them via future grants).
-- Idempotent: CREATE TABLE IF NOT EXISTS.
-- =====================================================================
USE ROLE LOADER_ROLE;
USE WAREHOUSE NOMAD_WH;
USE SCHEMA NOMAD_HUB.RAW;

-- OurAirports — ISO countries
CREATE TABLE IF NOT EXISTS COUNTRIES (
    ID             VARCHAR,
    CODE           VARCHAR,
    NAME           VARCHAR,
    CONTINENT      VARCHAR,
    WIKIPEDIA_LINK VARCHAR,
    KEYWORDS       VARCHAR,
    _SOURCE_FILE   VARCHAR,
    _LOADED_AT     TIMESTAMP_LTZ
)
COMMENT = 'OurAirports — ISO countries';

-- OurAirports — first-level regions (US states etc.)
CREATE TABLE IF NOT EXISTS REGIONS (
    ID             VARCHAR,
    CODE           VARCHAR,
    LOCAL_CODE     VARCHAR,
    NAME           VARCHAR,
    CONTINENT      VARCHAR,
    ISO_COUNTRY    VARCHAR,
    WIKIPEDIA_LINK VARCHAR,
    KEYWORDS       VARCHAR,
    _SOURCE_FILE   VARCHAR,
    _LOADED_AT     TIMESTAMP_LTZ
)
COMMENT = 'OurAirports — first-level regions (US states etc.)';

-- OurAirports — ~86K airports with coordinates and IATA codes
CREATE TABLE IF NOT EXISTS AIRPORTS (
    ID                VARCHAR,
    IDENT             VARCHAR,
    TYPE              VARCHAR,
    NAME              VARCHAR,
    LATITUDE_DEG      VARCHAR,
    LONGITUDE_DEG     VARCHAR,
    ELEVATION_FT      VARCHAR,
    CONTINENT         VARCHAR,
    ISO_COUNTRY       VARCHAR,
    ISO_REGION        VARCHAR,
    MUNICIPALITY      VARCHAR,
    SCHEDULED_SERVICE VARCHAR,
    ICAO_CODE         VARCHAR,
    IATA_CODE         VARCHAR,
    GPS_CODE          VARCHAR,
    LOCAL_CODE        VARCHAR,
    HOME_LINK         VARCHAR,
    WIKIPEDIA_LINK    VARCHAR,
    KEYWORDS          VARCHAR,
    _SOURCE_FILE      VARCHAR,
    _LOADED_AT        TIMESTAMP_LTZ
)
COMMENT = 'OurAirports — ~86K airports with coordinates and IATA codes';

-- Inside Airbnb — listings, one file per city snapshot (price is local currency)
CREATE TABLE IF NOT EXISTS LISTINGS (
    CITY                           VARCHAR,
    SNAPSHOT_DATE                  VARCHAR,
    LISTING_ID                     VARCHAR,
    LAST_SCRAPED                   VARCHAR,
    NAME                           VARCHAR,
    DESCRIPTION                    VARCHAR,
    HOST_ID                        VARCHAR,
    HOST_SINCE                     VARCHAR,
    HOST_RESPONSE_RATE             VARCHAR,
    HOST_ACCEPTANCE_RATE           VARCHAR,
    HOST_IS_SUPERHOST              VARCHAR,
    CALCULATED_HOST_LISTINGS_COUNT VARCHAR,
    NEIGHBOURHOOD_CLEANSED         VARCHAR,
    NEIGHBOURHOOD_GROUP_CLEANSED   VARCHAR,
    LATITUDE                       VARCHAR,
    LONGITUDE                      VARCHAR,
    PROPERTY_TYPE                  VARCHAR,
    ROOM_TYPE                      VARCHAR,
    ACCOMMODATES                   VARCHAR,
    BATHROOMS                      VARCHAR,
    BATHROOMS_TEXT                 VARCHAR,
    BEDROOMS                       VARCHAR,
    BEDS                           VARCHAR,
    AMENITIES                      VARCHAR,
    PRICE                          VARCHAR,
    MINIMUM_NIGHTS                 VARCHAR,
    MAXIMUM_NIGHTS                 VARCHAR,
    HAS_AVAILABILITY               VARCHAR,
    AVAILABILITY_30                VARCHAR,
    AVAILABILITY_90                VARCHAR,
    AVAILABILITY_365               VARCHAR,
    NUMBER_OF_REVIEWS              VARCHAR,
    NUMBER_OF_REVIEWS_LTM          VARCHAR,
    FIRST_REVIEW                   VARCHAR,
    LAST_REVIEW                    VARCHAR,
    REVIEW_SCORES_RATING           VARCHAR,
    REVIEW_SCORES_ACCURACY         VARCHAR,
    REVIEW_SCORES_CLEANLINESS      VARCHAR,
    REVIEW_SCORES_CHECKIN          VARCHAR,
    REVIEW_SCORES_COMMUNICATION    VARCHAR,
    REVIEW_SCORES_LOCATION         VARCHAR,
    REVIEW_SCORES_VALUE            VARCHAR,
    INSTANT_BOOKABLE               VARCHAR,
    LICENSE                        VARCHAR,
    ESTIMATED_OCCUPANCY_L365D      VARCHAR,
    ESTIMATED_REVENUE_L365D        VARCHAR,
    _SOURCE_FILE                   VARCHAR,
    _LOADED_AT                     TIMESTAMP_LTZ
)
COMMENT = 'Inside Airbnb — listings, one file per city snapshot (price is local currency)';

-- Inside Airbnb — 365-day forward availability per listing
CREATE TABLE IF NOT EXISTS CALENDAR (
    CITY           VARCHAR,
    SNAPSHOT_DATE  VARCHAR,
    LISTING_ID     VARCHAR,
    CALENDAR_DATE  VARCHAR,
    AVAILABLE      VARCHAR,
    MINIMUM_NIGHTS VARCHAR,
    MAXIMUM_NIGHTS VARCHAR,
    _SOURCE_FILE   VARCHAR,
    _LOADED_AT     TIMESTAMP_LTZ
)
COMMENT = 'Inside Airbnb — 365-day forward availability per listing';

-- Inside Airbnb — review text; full history repeats in every snapshot
CREATE TABLE IF NOT EXISTS REVIEWS (
    CITY          VARCHAR,
    SNAPSHOT_DATE VARCHAR,
    REVIEW_ID     VARCHAR,
    LISTING_ID    VARCHAR,
    REVIEW_DATE   VARCHAR,
    REVIEWER_ID   VARCHAR,
    COMMENTS      VARCHAR,
    _SOURCE_FILE  VARCHAR,
    _LOADED_AT    TIMESTAMP_LTZ
)
COMMENT = 'Inside Airbnb — review text; full history repeats in every snapshot';

-- BTS On-Time Performance — every US domestic flight, one file per month
CREATE TABLE IF NOT EXISTS FLIGHTS (
    FLIGHT_DATE         VARCHAR,
    REPORTING_AIRLINE   VARCHAR,
    AIRLINE_IATA_CODE   VARCHAR,
    TAIL_NUMBER         VARCHAR,
    FLIGHT_NUMBER       VARCHAR,
    ORIGIN              VARCHAR,
    ORIGIN_CITY_NAME    VARCHAR,
    ORIGIN_STATE        VARCHAR,
    DEST                VARCHAR,
    DEST_CITY_NAME      VARCHAR,
    DEST_STATE          VARCHAR,
    CRS_DEP_TIME        VARCHAR,
    DEP_TIME            VARCHAR,
    DEP_DELAY           VARCHAR,
    DEP_DELAY_MINUTES   VARCHAR,
    DEP_DEL15           VARCHAR,
    TAXI_OUT            VARCHAR,
    WHEELS_OFF          VARCHAR,
    WHEELS_ON           VARCHAR,
    TAXI_IN             VARCHAR,
    CRS_ARR_TIME        VARCHAR,
    ARR_TIME            VARCHAR,
    ARR_DELAY           VARCHAR,
    ARR_DELAY_MINUTES   VARCHAR,
    ARR_DEL15           VARCHAR,
    CANCELLED           VARCHAR,
    CANCELLATION_CODE   VARCHAR,
    DIVERTED            VARCHAR,
    CRS_ELAPSED_TIME    VARCHAR,
    ACTUAL_ELAPSED_TIME VARCHAR,
    AIR_TIME            VARCHAR,
    DISTANCE            VARCHAR,
    CARRIER_DELAY       VARCHAR,
    WEATHER_DELAY       VARCHAR,
    NAS_DELAY           VARCHAR,
    SECURITY_DELAY      VARCHAR,
    LATE_AIRCRAFT_DELAY VARCHAR,
    _SOURCE_FILE        VARCHAR,
    _LOADED_AT          TIMESTAMP_LTZ
)
COMMENT = 'BTS On-Time Performance — every US domestic flight, one file per month';

-- Synthetic — pseudonymised reviewers (data/generate_data.py)
CREATE TABLE IF NOT EXISTS USERS (
    USER_ID             VARCHAR,
    SOURCE_REVIEWER_ID  VARCHAR,
    FIRST_NAME          VARCHAR,
    LAST_NAME           VARCHAR,
    EMAIL               VARCHAR,
    GENDER              VARCHAR,
    BIRTH_DATE          VARCHAR,
    HOME_COUNTRY_CODE   VARCHAR,
    HOME_AIRPORT        VARCHAR,
    PREFERRED_LANGUAGE  VARCHAR,
    SIGNED_UP_AT        VARCHAR,
    ACQUISITION_CHANNEL VARCHAR,
    MARKETING_OPT_IN    VARCHAR,
    _SOURCE_FILE        VARCHAR,
    _LOADED_AT          TIMESTAMP_LTZ
)
COMMENT = 'Synthetic — pseudonymised reviewers (data/generate_data.py)';

-- Synthetic — one stay per real review + cancelled bookings
CREATE TABLE IF NOT EXISTS STAY_BOOKINGS (
    STAY_BOOKING_ID VARCHAR,
    USER_ID         VARCHAR,
    LISTING_ID      VARCHAR,
    CITY            VARCHAR,
    REVIEW_ID       VARCHAR,
    BOOKED_AT       VARCHAR,
    CHECKIN_DATE    VARCHAR,
    CHECKOUT_DATE   VARCHAR,
    NIGHTS          VARCHAR,
    GUESTS          VARCHAR,
    CURRENCY_CODE   VARCHAR,
    NIGHTLY_RATE    VARCHAR,
    CLEANING_FEE    VARCHAR,
    SERVICE_FEE     VARCHAR,
    TOTAL_AMOUNT    VARCHAR,
    PAYMENT_METHOD  VARCHAR,
    BOOKING_CHANNEL VARCHAR,
    BOOKING_STATUS  VARCHAR,
    CANCELLED_AT    VARCHAR,
    REFUND_AMOUNT   VARCHAR,
    _SOURCE_FILE    VARCHAR,
    _LOADED_AT      TIMESTAMP_LTZ
)
COMMENT = 'Synthetic — one stay per real review + cancelled bookings';

-- Synthetic — users booked onto real BTS flights
CREATE TABLE IF NOT EXISTS FLIGHT_BOOKINGS (
    FLIGHT_BOOKING_ID      VARCHAR,
    STAY_BOOKING_ID        VARCHAR,
    USER_ID                VARCHAR,
    LEG                    VARCHAR,
    BOOKED_AT              VARCHAR,
    FLIGHT_DATE            VARCHAR,
    AIRLINE_CODE           VARCHAR,
    FLIGHT_NUMBER          VARCHAR,
    ORIGIN                 VARCHAR,
    DEST                   VARCHAR,
    CRS_DEP_TIME           VARCHAR,
    CABIN_CLASS            VARCHAR,
    PASSENGERS             VARCHAR,
    FARE_PER_PASSENGER_USD VARCHAR,
    TOTAL_FARE_USD         VARCHAR,
    BOOKING_STATUS         VARCHAR,
    _SOURCE_FILE           VARCHAR,
    _LOADED_AT             TIMESTAMP_LTZ
)
COMMENT = 'Synthetic — users booked onto real BTS flights';
