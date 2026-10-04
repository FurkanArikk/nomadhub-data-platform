# ── Data lake bucket ─────────────────────────────────────────────────────────
# s3://<bucket>/raw/<table>/<partition>/<file>.csv.gz — same layout as data/raw/

resource "aws_s3_bucket" "lake" {
  bucket = var.bucket_name
  # Sandbox convenience: `terraform destroy` also deletes the objects (all versions).
  # The data is reproducible from data/raw/; set false for anything you can't rebuild.
  force_destroy = true
}

resource "aws_s3_bucket_ownership_controls" "lake" {
  bucket = aws_s3_bucket.lake.id
  rule {
    object_ownership = "BucketOwnerEnforced" # ACLs off; the bucket policy/IAM decide access
  }
}

resource "aws_s3_bucket_public_access_block" "lake" {
  bucket                  = aws_s3_bucket.lake.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "lake" {
  bucket = aws_s3_bucket.lake.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "lake" {
  bucket = aws_s3_bucket.lake.id
  versioning_configuration {
    status = "Enabled" # an accidental overwrite/delete of raw data is recoverable
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "lake" {
  bucket     = aws_s3_bucket.lake.id
  depends_on = [aws_s3_bucket_versioning.lake]

  rule {
    id     = "expire-old-versions-and-failed-uploads"
    status = "Enabled"
    filter {}

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

# ── Snowflake ↔ S3 trust (the "storage integration handshake") ───────────────
# Snowflake assumes this role to read raw/. Its trust policy needs two values that only
# exist after the storage integration is created (Snowflake's IAM user + external ID).
# Done by hand that is a 4-step back-and-forth; here Terraform wires the outputs of
# snowflake_storage_integration_aws.s3 straight into the trust policy. The integration only
# needs the role's ARN, which we can compute up front — so there is no dependency cycle.

data "aws_caller_identity" "current" {}

locals {
  snowflake_role_name = "nomadhub-snowflake-s3-read"
  snowflake_role_arn  = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/${local.snowflake_role_name}"
}

data "aws_iam_policy_document" "snowflake_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "AWS"
      identifiers = [snowflake_storage_integration_aws.s3.describe_output[0].iam_user_arn]
    }
    condition {
      test     = "StringEquals"
      variable = "sts:ExternalId"
      values   = [snowflake_storage_integration_aws.s3.describe_output[0].external_id]
    }
  }
}

data "aws_iam_policy_document" "snowflake_read" {
  statement {
    sid       = "ReadRawObjects"
    actions   = ["s3:GetObject", "s3:GetObjectVersion"]
    resources = ["${aws_s3_bucket.lake.arn}/raw/*"]
  }
  statement {
    sid       = "ListRawPrefix"
    actions   = ["s3:ListBucket", "s3:GetBucketLocation"]
    resources = [aws_s3_bucket.lake.arn]
    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["raw/*", "raw/"]
    }
  }
}

resource "aws_iam_role" "snowflake" {
  name               = local.snowflake_role_name
  description        = "Assumed by Snowflake storage integration NOMAD_S3_INT to read the raw/ prefix"
  assume_role_policy = data.aws_iam_policy_document.snowflake_trust.json
}

resource "aws_iam_role_policy" "snowflake_read" {
  name   = "read-raw-prefix"
  role   = aws_iam_role.snowflake.id
  policy = data.aws_iam_policy_document.snowflake_read.json
}
