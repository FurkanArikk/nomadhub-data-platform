-- =====================================================================
-- NomadHub — one-time bootstrap (the ONLY SQL you run by hand)
-- Creates the service user Terraform logs in with. Everything else
-- (warehouse, database, schemas, roles, users, S3 integration, stage)
-- is created by `terraform apply` — see CLOUD.md.
--
-- 1. Run scripts/generate_snowflake_keys.sh and copy the printed public key.
-- 2. Paste it between the quotes below.
-- 3. Run this whole worksheet in Snowsight as ACCOUNTADMIN.
-- =====================================================================
USE ROLE ACCOUNTADMIN;

CREATE USER IF NOT EXISTS TERRAFORM_SVC
    TYPE           = SERVICE          -- no password, no MFA prompts: key-pair only
    RSA_PUBLIC_KEY = '<PASTE_TERRAFORM_SVC_PUBLIC_KEY_HERE>'
    DEFAULT_ROLE   = ACCOUNTADMIN
    COMMENT        = 'Terraform for the NomadHub project';

-- Terraform creates account-level objects (integration, resource monitor, users),
-- which need ACCOUNTADMIN. Fine for a personal trial account; in a company you would
-- split this across SYSADMIN / SECURITYADMIN and a custom role with CREATE INTEGRATION.
GRANT ROLE ACCOUNTADMIN TO USER TERRAFORM_SVC;

-- The two values terraform.tfvars needs:
SELECT CURRENT_ORGANIZATION_NAME() AS snowflake_organization_name,
       CURRENT_ACCOUNT_NAME()      AS snowflake_account_name,
       CURRENT_USER()              AS snowflake_human_user,
       CURRENT_REGION()            AS region;
