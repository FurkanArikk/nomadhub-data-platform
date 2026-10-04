variable "aws_region" {
  description = "AWS region for the bucket. Use the same region as your Snowflake account (free, fast transfer)."
  type        = string
  default     = "eu-central-1"
}

variable "aws_profile" {
  description = "Named AWS CLI profile Terraform uses (aws configure --profile <name>)."
  type        = string
  default     = "nomadhub"
}

variable "bucket_name" {
  description = "Globally unique S3 bucket name for the data lake, e.g. nomadhub-<yourname>-raw."
  type        = string
}

variable "snowflake_organization_name" {
  description = "First half of the account identifier ORGNAME-ACCOUNTNAME (Snowsight → profile → Account)."
  type        = string
}

variable "snowflake_account_name" {
  description = "Second half of the account identifier ORGNAME-ACCOUNTNAME."
  type        = string
}

variable "snowflake_key_dir" {
  description = "Directory with the RSA key pairs from scripts/generate_snowflake_keys.sh."
  type        = string
  default     = "~/.nomadhub/keys"
}

variable "snowflake_human_user" {
  description = "Your own Snowflake login. Gets the project roles so you can explore in Snowsight. Empty = skip."
  type        = string
  default     = ""
}

variable "monthly_credit_quota" {
  description = "Resource monitor cap. The warehouse is suspended when this many credits are used in a month."
  type        = number
  default     = 50
}
