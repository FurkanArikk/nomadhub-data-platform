-- ============================================================
-- NomadHub Snowflake Setup — Step 03: Stage & File Formats
-- ============================================================

USE ROLE NOMAD_ADMIN;
USE WAREHOUSE NOMAD_WH;
USE DATABASE NOMAD_HUB;
USE SCHEMA RAW;

-- ── 1. CSV File Format ────────────────────────────────────────────────────────
CREATE OR REPLACE FILE FORMAT NOMAD_CSV_FORMAT
    TYPE                 = 'CSV'
    FIELD_DELIMITER      = ','
    RECORD_DELIMITER     = '\n'
    SKIP_HEADER          = 1
    FIELD_OPTIONALLY_ENCLOSED_BY = '"'
    NULL_IF              = ('', 'NULL', 'null', 'None', 'NA')
    EMPTY_FIELD_AS_NULL  = TRUE
    TRIM_SPACE           = TRUE
    DATE_FORMAT          = 'YYYY-MM-DD'
    TIMESTAMP_FORMAT     = 'YYYY-MM-DD HH24:MI:SS'
    COMPRESSION          = 'AUTO'
    COMMENT = 'Standard CSV format for NomadHub data files';

-- ── 2. External Stage (points to S3 via storage integration) ─────────────────
CREATE OR REPLACE STAGE NOMAD_S3_STAGE
    URL                = 's3://YOUR-NOMAD-HUB-BUCKET/raw/'
    STORAGE_INTEGRATION = NOMAD_S3_INTEGRATION
    FILE_FORMAT        = NOMAD_CSV_FORMAT
    COMMENT = 'External stage: S3 raw/ prefix';

-- ── 3. Verify stage ───────────────────────────────────────────────────────────
LIST @NOMAD_S3_STAGE;
-- Expected output: 7 CSV files (countries/, airports/, hotels/, users/,
--                               flights/, hotel_bookings/, reviews/)

-- ── 4. Stage grants ───────────────────────────────────────────────────────────
GRANT READ ON STAGE NOMAD_HUB.RAW.NOMAD_S3_STAGE TO ROLE DBT_ROLE;
GRANT USAGE ON FILE FORMAT NOMAD_HUB.RAW.NOMAD_CSV_FORMAT TO ROLE DBT_ROLE;
