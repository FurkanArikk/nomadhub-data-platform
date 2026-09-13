-- ============================================================
-- NomadHub Snowflake Setup — Step 05: COPY INTO (Bronze Load)
-- ============================================================
-- Load CSV files from S3 stage into RAW tables.
-- Run AFTER: 03_stage_and_formats.sql + 04_raw_tables.sql
-- ============================================================

USE ROLE NOMAD_ADMIN;
USE WAREHOUSE NOMAD_WH;
USE DATABASE NOMAD_HUB;
USE SCHEMA RAW;

-- ── Load: countries ──────────────────────────────────────────────────────────
COPY INTO RAW.COUNTRIES
FROM @RAW.NOMAD_S3_STAGE/countries/
FILE_FORMAT = (FORMAT_NAME = RAW.NOMAD_CSV_FORMAT)
ON_ERROR    = 'ABORT_STATEMENT'
PURGE       = FALSE;

-- ── Load: airports ────────────────────────────────────────────────────────────
COPY INTO RAW.AIRPORTS
FROM @RAW.NOMAD_S3_STAGE/airports/
FILE_FORMAT = (FORMAT_NAME = RAW.NOMAD_CSV_FORMAT)
ON_ERROR    = 'ABORT_STATEMENT'
PURGE       = FALSE;

-- ── Load: hotels ──────────────────────────────────────────────────────────────
COPY INTO RAW.HOTELS
FROM @RAW.NOMAD_S3_STAGE/hotels/
FILE_FORMAT = (FORMAT_NAME = RAW.NOMAD_CSV_FORMAT)
ON_ERROR    = 'ABORT_STATEMENT'
PURGE       = FALSE;

-- ── Load: users ───────────────────────────────────────────────────────────────
COPY INTO RAW.USERS
FROM @RAW.NOMAD_S3_STAGE/users/
FILE_FORMAT = (FORMAT_NAME = RAW.NOMAD_CSV_FORMAT)
ON_ERROR    = 'ABORT_STATEMENT'
PURGE       = FALSE;

-- ── Load: flights (large — may take 2-5 min) ─────────────────────────────────
COPY INTO RAW.FLIGHTS
FROM @RAW.NOMAD_S3_STAGE/flights/
FILE_FORMAT = (FORMAT_NAME = RAW.NOMAD_CSV_FORMAT)
ON_ERROR    = 'CONTINUE'       -- skip bad rows, log errors
PURGE       = FALSE;

-- ── Load: hotel_bookings (large — may take 3-7 min) ──────────────────────────
COPY INTO RAW.HOTEL_BOOKINGS
FROM @RAW.NOMAD_S3_STAGE/hotel_bookings/
FILE_FORMAT = (FORMAT_NAME = RAW.NOMAD_CSV_FORMAT)
ON_ERROR    = 'CONTINUE'
PURGE       = FALSE;

-- ── Load: reviews ─────────────────────────────────────────────────────────────
COPY INTO RAW.REVIEWS
FROM @RAW.NOMAD_S3_STAGE/reviews/
FILE_FORMAT = (FORMAT_NAME = RAW.NOMAD_CSV_FORMAT)
ON_ERROR    = 'ABORT_STATEMENT'
PURGE       = FALSE;

-- ── Load monitoring ───────────────────────────────────────────────────────────
-- Check row counts
SELECT 'countries'     AS tbl, COUNT(*) AS rows FROM RAW.COUNTRIES       UNION ALL
SELECT 'airports',              COUNT(*)         FROM RAW.AIRPORTS        UNION ALL
SELECT 'hotels',                COUNT(*)         FROM RAW.HOTELS          UNION ALL
SELECT 'users',                 COUNT(*)         FROM RAW.USERS           UNION ALL
SELECT 'flights',               COUNT(*)         FROM RAW.FLIGHTS         UNION ALL
SELECT 'hotel_bookings',        COUNT(*)         FROM RAW.HOTEL_BOOKINGS  UNION ALL
SELECT 'reviews',               COUNT(*)         FROM RAW.REVIEWS
ORDER BY 1;

-- Check COPY history (last 24h)
SELECT
    TABLE_NAME,
    FILE_NAME,
    ROW_COUNT,
    ROW_PARSED,
    FIRST_ERROR_MESSAGE,
    STATUS,
    LAST_LOAD_TIME
FROM INFORMATION_SCHEMA.LOAD_HISTORY
WHERE SCHEMA_NAME = 'RAW'
  AND LAST_LOAD_TIME >= DATEADD(hour, -24, CURRENT_TIMESTAMP())
ORDER BY LAST_LOAD_TIME DESC;
