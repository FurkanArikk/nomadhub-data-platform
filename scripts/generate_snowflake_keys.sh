#!/usr/bin/env bash
# Generate RSA key pairs for the Snowflake service users (key-pair auth, no passwords).
#
#   terraform_svc  → used by Terraform; its public key goes into snowflake/00_bootstrap_terraform.sql
#   airflow_svc, dbt_svc, streamlit_svc → public keys are registered by Terraform
#
# Keys are written OUTSIDE the repo (default ~/.nomadhub/keys) and never committed.
# Existing keys are left untouched, so re-running is safe.
set -euo pipefail

KEY_DIR="${1:-$HOME/.nomadhub/keys}"
USERS=(terraform_svc airflow_svc dbt_svc streamlit_svc)

mkdir -p "$KEY_DIR"
chmod 700 "$KEY_DIR"

for user in "${USERS[@]}"; do
  private="$KEY_DIR/${user}_rsa_key.p8"
  public="$KEY_DIR/${user}_rsa_key.pub"
  if [[ -f "$private" ]]; then
    echo "• $user: key exists, skipped"
    continue
  fi
  openssl genrsa 2048 2>/dev/null | openssl pkcs8 -topk8 -inform PEM -out "$private" -nocrypt
  openssl rsa -in "$private" -pubout -out "$public" 2>/dev/null
  chmod 600 "$private"
  echo "✓ $user: $private"
done

echo
echo "Public key for snowflake/00_bootstrap_terraform.sql (paste between the quotes):"
echo
grep -v -- "-----" "$KEY_DIR/terraform_svc_rsa_key.pub" | tr -d '\n'
echo
