output "bucket_name" {
  description = "Data lake bucket — upload data/raw/ to s3://<bucket>/raw/"
  value       = aws_s3_bucket.lake.bucket
}

output "snowflake_s3_role_arn" {
  description = "IAM role Snowflake assumes to read raw/"
  value       = aws_iam_role.snowflake.arn
}

output "snowflake_account" {
  description = "Account identifier for connectors (SNOWFLAKE_ACCOUNT)"
  value       = "${var.snowflake_organization_name}-${var.snowflake_account_name}"
}

output "raw_stage" {
  description = "External stage pointing at s3://<bucket>/raw/"
  value       = snowflake_stage_external_s3.raw.fully_qualified_name
}

output "service_users" {
  description = "Service users and their roles; private keys live in var.snowflake_key_dir"
  value       = local.service_users
}
