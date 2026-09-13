-- ============================================================
-- NomadHub Snowflake Setup — Step 02: S3 Storage Integration
-- ============================================================
-- Keyless S3 connection: Snowflake assumes an IAM role in your
-- AWS account — no long-lived access keys needed.
--
-- Prerequisites:
--   • S3 bucket created: s3://YOUR-NOMAD-HUB-BUCKET/
--   • aws/iam/s3_policy.json applied to an IAM role
--
-- Steps:
--   1. Run CREATE STORAGE INTEGRATION below
--   2. Run DESCRIBE INTEGRATION to get STORAGE_AWS_IAM_USER_ARN
--      and STORAGE_AWS_EXTERNAL_ID
--   3. Update your IAM role's trust policy with these values
--   4. Run the verification query at the bottom
-- ============================================================

USE ROLE NOMAD_ADMIN;
USE WAREHOUSE NOMAD_WH;
USE DATABASE NOMAD_HUB;

-- ── 1. Storage Integration ────────────────────────────────────────────────────
CREATE STORAGE INTEGRATION IF NOT EXISTS NOMAD_S3_INTEGRATION
    TYPE                   = EXTERNAL_STAGE
    STORAGE_PROVIDER       = 'S3'
    ENABLED                = TRUE
    STORAGE_AWS_ROLE_ARN   = 'arn:aws:iam::YOUR_AWS_ACCOUNT_ID:role/YOUR_SNOWFLAKE_ROLE'
    STORAGE_ALLOWED_LOCATIONS = ('s3://YOUR-NOMAD-HUB-BUCKET/raw/')
    COMMENT = 'NomadHub keyless S3 integration';

-- ── 2. Get IAM values for trust policy ───────────────────────────────────────
-- Copy STORAGE_AWS_IAM_USER_ARN and STORAGE_AWS_EXTERNAL_ID from output
DESCRIBE INTEGRATION NOMAD_S3_INTEGRATION;

-- ── 3. Grant integration to DBT_ROLE ─────────────────────────────────────────
GRANT USAGE ON INTEGRATION NOMAD_S3_INTEGRATION TO ROLE DBT_ROLE;

-- ── 4. IAM Trust Policy template ─────────────────────────────────────────────
-- After DESCRIBE above, update your IAM role's trust policy to:
--
-- {
--   "Version": "2012-10-17",
--   "Statement": [
--     {
--       "Effect": "Allow",
--       "Principal": {
--         "AWS": "<STORAGE_AWS_IAM_USER_ARN from DESCRIBE output>"
--       },
--       "Action": "sts:AssumeRole",
--       "Condition": {
--         "StringEquals": {
--           "sts:ExternalId": "<STORAGE_AWS_EXTERNAL_ID from DESCRIBE output>"
--         }
--       }
--     }
--   ]
-- }

-- ── 5. Verify connection ──────────────────────────────────────────────────────
-- After updating the trust policy, test access:
LIST @NOMAD_HUB.RAW.NOMAD_S3_STAGE;
-- Should list your CSV files. If empty, upload data first with aws/upload_to_s3.py
