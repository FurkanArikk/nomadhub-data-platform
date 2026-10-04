terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.67"
    }
    snowflake = {
      source  = "snowflakedb/snowflake"
      version = "~> 2.21"
    }
  }
}

provider "aws" {
  region  = var.aws_region
  profile = var.aws_profile

  default_tags {
    tags = {
      Project   = "nomadhub"
      ManagedBy = "terraform"
    }
  }
}

# Terraform logs in as TERRAFORM_SVC (created once by snowflake/00_bootstrap_terraform.sql)
# with key-pair auth — no password anywhere.
provider "snowflake" {
  organization_name = var.snowflake_organization_name
  account_name      = var.snowflake_account_name
  user              = "TERRAFORM_SVC"
  role              = "ACCOUNTADMIN"
  authenticator     = "SNOWFLAKE_JWT"
  private_key       = file(pathexpand("${var.snowflake_key_dir}/terraform_svc_rsa_key.p8"))

  # Storage integration, stage and file format are still "preview" resources in provider 2.x.
  preview_features_enabled = [
    "snowflake_storage_integration_aws_resource",
    "snowflake_stage_external_s3_resource",
    "snowflake_file_format_csv_resource",
  ]
}
