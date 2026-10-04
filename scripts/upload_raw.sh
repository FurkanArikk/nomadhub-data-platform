#!/usr/bin/env bash
# Sync data/raw/ to s3://<bucket>/raw/ (same layout). Only new or changed files are
# uploaded, so re-running after new downloads/generation is cheap.
#
#   scripts/upload_raw.sh                 # bucket read from `terraform output`
#   scripts/upload_raw.sh my-bucket-name  # explicit bucket
#   AWS_PROFILE=other scripts/upload_raw.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUCKET="${1:-$(terraform -chdir="$ROOT/terraform" output -raw bucket_name)}"
PROFILE="${AWS_PROFILE:-nomadhub}"

echo "Uploading $ROOT/data/raw/ → s3://$BUCKET/raw/ (profile: $PROFILE)"
aws s3 sync "$ROOT/data/raw/" "s3://$BUCKET/raw/" \
  --profile "$PROFILE" \
  --exclude "*.part" \
  --only-show-errors

echo "Done. Objects under raw/:"
aws s3 ls "s3://$BUCKET/raw/" --recursive --summarize --human-readable --profile "$PROFILE" | tail -2
