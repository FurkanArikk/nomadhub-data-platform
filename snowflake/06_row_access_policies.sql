-- ============================================================
-- NomadHub Snowflake Setup — Step 06: Row Access Policies
-- ============================================================
-- Demonstrates row-level security — ANALYST_ROLE can only
-- read "completed" bookings; NOMAD_ADMIN sees everything.
-- This is an OPTIONAL advanced security feature.
-- ============================================================

USE ROLE NOMAD_ADMIN;
USE DATABASE NOMAD_HUB;
USE SCHEMA MARTS;

-- ── 1. Row Access Policy: restrict analysts to completed bookings only ────────
CREATE OR REPLACE ROW ACCESS POLICY BOOKING_STATUS_POLICY
AS (booking_status VARCHAR) RETURNS BOOLEAN ->
    CASE
        -- Admin and DBT can see all rows
        WHEN CURRENT_ROLE() IN ('NOMAD_ADMIN', 'DBT_ROLE', 'SYSADMIN', 'ACCOUNTADMIN')
            THEN TRUE
        -- Analyst can only see completed bookings (not cancelled, no_show)
        WHEN CURRENT_ROLE() = 'ANALYST_ROLE' AND booking_status = 'completed'
            THEN TRUE
        ELSE FALSE
    END
COMMENT = 'Analysts only see completed bookings';

-- ── 2. Apply policy to fact tables ───────────────────────────────────────────
-- NOTE: Apply AFTER dbt has created these tables
-- ALTER TABLE MARTS.FCT_FLIGHTS        ADD ROW ACCESS POLICY BOOKING_STATUS_POLICY ON (BOOKING_STATUS);
-- ALTER TABLE MARTS.FCT_HOTEL_BOOKINGS ADD ROW ACCESS POLICY BOOKING_STATUS_POLICY ON (BOOKING_STATUS);

-- ── 3. Column masking policy: hide PII from analysts ─────────────────────────
CREATE OR REPLACE MASKING POLICY EMAIL_MASK
AS (email_val VARCHAR) RETURNS VARCHAR ->
    CASE
        WHEN CURRENT_ROLE() IN ('NOMAD_ADMIN', 'DBT_ROLE') THEN email_val
        -- Analysts see only the domain, not the full email
        ELSE CONCAT('***@', SPLIT_PART(email_val, '@', 2))
    END
COMMENT = 'Mask email addresses for ANALYST_ROLE';

CREATE OR REPLACE MASKING POLICY PHONE_MASK
AS (phone_val VARCHAR) RETURNS VARCHAR ->
    CASE
        WHEN CURRENT_ROLE() IN ('NOMAD_ADMIN', 'DBT_ROLE') THEN phone_val
        ELSE '***-***-****'
    END
COMMENT = 'Mask phone numbers for ANALYST_ROLE';

-- Apply to DIM_USERS after dbt creates it:
-- ALTER TABLE MARTS.DIM_USERS MODIFY COLUMN EMAIL  SET MASKING POLICY EMAIL_MASK;
-- ALTER TABLE MARTS.DIM_USERS MODIFY COLUMN PHONE  SET MASKING POLICY PHONE_MASK;

-- ── 4. Verify policies ────────────────────────────────────────────────────────
SHOW ROW ACCESS POLICIES IN SCHEMA NOMAD_HUB.MARTS;
SHOW MASKING POLICIES IN SCHEMA NOMAD_HUB.MARTS;

-- ── 5. Network policy (optional) — restrict by IP ────────────────────────────
-- Uncomment and configure to allow access only from known IPs:
--
-- CREATE OR REPLACE NETWORK POLICY NOMAD_NETWORK_POLICY
--   ALLOWED_IP_LIST   = ('203.0.113.0/24', '198.51.100.10')  -- your office/VPN IPs
--   BLOCKED_IP_LIST   = ()
--   COMMENT = 'Restrict Snowflake access to known IP ranges';
--
-- ALTER ACCOUNT SET NETWORK_POLICY = NOMAD_NETWORK_POLICY;
