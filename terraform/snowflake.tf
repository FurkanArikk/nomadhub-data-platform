# ═════════════════════════════════════════════════════════════════════════════
# Snowflake: compute, storage layers, access model, S3 link
#
#   LOADER_ROLE   COPY INTO RAW from the S3 stage            (Airflow)
#   DBT_ROLE      read RAW, build STAGING/MARTS/SNAPSHOTS/AI  (dbt, AI enrichment)
#   ANALYST_ROLE  read-only STAGING/MARTS/AI                  (Streamlit, text-to-SQL)
#
# Objects are owned by ACCOUNTADMIN (Terraform's role); the three roles get only the
# privileges listed below. RAW tables are created by LOADER_ROLE at load time (they
# belong to the pipeline, see snowflake/01_raw_tables.sql), so their reads are granted
# via FUTURE grants.
# ═════════════════════════════════════════════════════════════════════════════

locals {
  database = "NOMAD_HUB"
  schemas = {
    RAW       = "Bronze: files from s3://<bucket>/raw/ loaded as-is by COPY INTO"
    STAGING   = "Silver: dbt views — cleaned, typed, deduplicated"
    MARTS     = "Gold: dbt dimensions, incremental facts and business marts"
    SNAPSHOTS = "dbt SCD2 snapshots"
    AI        = "LLM-enriched tables (Gemini) and AI marts"
  }
  roles = {
    LOADER_ROLE  = "Loads RAW from the S3 stage (Airflow)"
    DBT_ROLE     = "Transforms RAW into STAGING/MARTS/SNAPSHOTS/AI (dbt + enrichment)"
    ANALYST_ROLE = "Read-only access for dashboards and text-to-SQL"
  }
  # service user -> roles (first one is the default role)
  service_users = {
    AIRFLOW_SVC   = ["LOADER_ROLE", "DBT_ROLE"]
    DBT_SVC       = ["DBT_ROLE"]
    STREAMLIT_SVC = ["ANALYST_ROLE"]
  }

  # role -> schema -> privileges on the schema itself
  schema_grants = {
    LOADER_ROLE = { RAW = ["USAGE", "CREATE TABLE"] }
    DBT_ROLE = {
      RAW       = ["USAGE"]
      STAGING   = ["USAGE", "CREATE TABLE", "CREATE VIEW"]
      MARTS     = ["USAGE", "CREATE TABLE", "CREATE VIEW"]
      SNAPSHOTS = ["USAGE", "CREATE TABLE", "CREATE VIEW"]
      AI        = ["USAGE", "CREATE TABLE", "CREATE VIEW"]
    }
    ANALYST_ROLE = { STAGING = ["USAGE"], MARTS = ["USAGE"], AI = ["USAGE"] }
  }
  # role -> schemas whose future tables AND views it may SELECT
  future_select = {
    DBT_ROLE     = ["RAW"]
    ANALYST_ROLE = ["STAGING", "MARTS", "AI"]
  }

  schema_grant_list = flatten([
    for role, schemas in local.schema_grants : [
      for schema, privs in schemas : { key = "${role}.${schema}", role = role, schema = schema, privs = privs }
    ]
  ])
  future_select_list = flatten([
    for role, schemas in local.future_select : [
      for schema in schemas : [
        for kind in ["TABLES", "VIEWS"] : { key = "${role}.${schema}.${kind}", role = role, schema = schema, kind = kind }
      ]
    ]
  ])
  user_role_list = flatten([
    for user, roles in local.service_users : [for role in roles : { key = "${user}.${role}", user = user, role = role }]
  ])
}

# ── Compute + cost guardrail ─────────────────────────────────────────────────

resource "snowflake_resource_monitor" "nomad" {
  name            = "NOMAD_MONITOR"
  credit_quota    = var.monthly_credit_quota
  frequency       = "MONTHLY"
  start_timestamp = "IMMEDIATELY"

  notify_triggers           = [50, 80]
  suspend_trigger           = 100 # finish running queries, then suspend
  suspend_immediate_trigger = 110 # cancel everything
}

resource "snowflake_warehouse" "nomad" {
  name                = "NOMAD_WH"
  warehouse_size      = "XSMALL"
  auto_suspend        = 60
  auto_resume         = true
  initially_suspended = true
  resource_monitor    = snowflake_resource_monitor.nomad.name
  comment             = "NomadHub pipeline + BI warehouse"
}

# ── Storage layers ───────────────────────────────────────────────────────────

resource "snowflake_database" "nomad" {
  name                           = local.database
  drop_public_schema_on_creation = true
  comment                        = "NomadHub travel data platform"
}

resource "snowflake_schema" "layer" {
  for_each = local.schemas
  database = snowflake_database.nomad.name
  name     = each.key
  comment  = each.value
}

# ── Roles and their hierarchy ────────────────────────────────────────────────

resource "snowflake_account_role" "role" {
  for_each = local.roles
  name     = each.key
  comment  = each.value
}

resource "snowflake_grant_account_role" "to_sysadmin" {
  for_each         = local.roles
  role_name        = snowflake_account_role.role[each.key].name
  parent_role_name = "SYSADMIN" # standard practice: custom roles roll up to SYSADMIN
}

resource "snowflake_grant_account_role" "to_human" {
  for_each  = var.snowflake_human_user == "" ? {} : local.roles
  role_name = snowflake_account_role.role[each.key].name
  user_name = var.snowflake_human_user
}

# ── Privileges ───────────────────────────────────────────────────────────────

resource "snowflake_grant_privileges_to_account_role" "warehouse" {
  for_each          = local.roles
  account_role_name = snowflake_account_role.role[each.key].name
  privileges        = ["USAGE", "OPERATE"]
  on_account_object {
    object_type = "WAREHOUSE"
    object_name = snowflake_warehouse.nomad.name
  }
}

resource "snowflake_grant_privileges_to_account_role" "database" {
  for_each          = local.roles
  account_role_name = snowflake_account_role.role[each.key].name
  privileges        = ["USAGE"]
  on_account_object {
    object_type = "DATABASE"
    object_name = snowflake_database.nomad.name
  }
}

resource "snowflake_grant_privileges_to_account_role" "schema" {
  for_each          = { for g in local.schema_grant_list : g.key => g }
  account_role_name = snowflake_account_role.role[each.value.role].name
  privileges        = each.value.privs
  on_schema {
    schema_name = snowflake_schema.layer[each.value.schema].fully_qualified_name
  }
}

resource "snowflake_grant_privileges_to_account_role" "future_select" {
  for_each          = { for g in local.future_select_list : g.key => g }
  account_role_name = snowflake_account_role.role[each.value.role].name
  privileges        = ["SELECT"]
  on_schema_object {
    future {
      object_type_plural = each.value.kind
      in_schema          = snowflake_schema.layer[each.value.schema].fully_qualified_name
    }
  }
}

# ── S3 link: integration → stage → file format ──────────────────────────────

resource "snowflake_storage_integration_aws" "s3" {
  name                      = "NOMAD_S3_INT"
  enabled                   = true
  storage_provider          = "S3"
  storage_aws_role_arn      = local.snowflake_role_arn
  storage_allowed_locations = ["s3://${aws_s3_bucket.lake.bucket}/raw/"]
  comment                   = "Keyless read access to the NomadHub raw/ prefix (assumes ${local.snowflake_role_name})"
}

resource "snowflake_file_format_csv" "raw" {
  database = snowflake_database.nomad.name
  schema   = snowflake_schema.layer["RAW"].name
  name     = "CSV_GZ"

  compression                    = "GZIP"
  skip_header                    = 1
  field_optionally_enclosed_by   = "\""
  multi_line                     = "true" # review/listing text may contain quoted newlines
  escape_unenclosed_field        = "NONE" # keep backslashes in free text as-is
  empty_field_as_null            = "true"
  null_if                        = [""]
  error_on_column_count_mismatch = "true" # every file of a table has the same layout
  encoding                       = "UTF8"
  comment                        = "gzip CSV with header, as written by data/download_sources.py + generate_data.py"
}

resource "snowflake_stage_external_s3" "raw" {
  database            = snowflake_database.nomad.name
  schema              = snowflake_schema.layer["RAW"].name
  name                = "RAW_STAGE"
  url                 = "s3://${aws_s3_bucket.lake.bucket}/raw/"
  storage_integration = snowflake_storage_integration_aws.s3.name
  comment             = "s3://${aws_s3_bucket.lake.bucket}/raw/ — one folder per table"

  file_format {
    format_name = snowflake_file_format_csv.raw.fully_qualified_name
  }

  # The IAM role must trust Snowflake before the stage is used.
  depends_on = [aws_iam_role_policy.snowflake_read]
}

resource "snowflake_grant_privileges_to_account_role" "loader_stage" {
  account_role_name = snowflake_account_role.role["LOADER_ROLE"].name
  privileges        = ["USAGE"]
  on_schema_object {
    object_type = "STAGE"
    object_name = snowflake_stage_external_s3.raw.fully_qualified_name
  }
}

resource "snowflake_grant_privileges_to_account_role" "loader_file_format" {
  account_role_name = snowflake_account_role.role["LOADER_ROLE"].name
  privileges        = ["USAGE"]
  on_schema_object {
    object_type = "FILE FORMAT"
    object_name = snowflake_file_format_csv.raw.fully_qualified_name
  }
}

# ── Service users (key-pair auth, no passwords) ──────────────────────────────

locals {
  # Snowflake wants the public key body without the PEM header/footer or newlines.
  public_keys = {
    for user in keys(local.service_users) : user => replace(replace(replace(
      file(pathexpand("${var.snowflake_key_dir}/${lower(user)}_rsa_key.pub")),
    "-----BEGIN PUBLIC KEY-----", ""), "-----END PUBLIC KEY-----", ""), "\n", "")
  }
}

resource "snowflake_service_user" "svc" {
  for_each          = local.service_users
  name              = each.key
  default_role      = each.value[0]
  default_warehouse = snowflake_warehouse.nomad.name
  default_namespace = snowflake_database.nomad.name
  rsa_public_key    = local.public_keys[each.key]
  comment           = "NomadHub service user (key-pair auth)"
}

resource "snowflake_grant_account_role" "to_service_user" {
  for_each  = { for g in local.user_role_list : g.key => g }
  role_name = snowflake_account_role.role[each.value.role].name
  user_name = snowflake_service_user.svc[each.value.user].name
}
