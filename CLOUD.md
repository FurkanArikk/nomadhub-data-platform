# Cloud setup — AWS + Snowflake

This guide takes you from zero to a loaded Snowflake warehouse: an S3 data lake, a
Snowflake account wired to it without any stored keys, and ~294M rows in the RAW layer.

Almost everything is code. You click through two sign-ups and paste one SQL block;
**Terraform** creates the rest, and `terraform destroy` removes it again.

```
 data/raw/ ──(scripts/upload_raw.sh)──▶ S3  s3://<bucket>/raw/<table>/...
                                          │
                     IAM role nomadhub-snowflake-s3-read   (trusts only Snowflake's IAM user
                                          │                 + your integration's external ID)
                                          ▼
 Snowflake  NOMAD_S3_INT ─▶ RAW.RAW_STAGE ─(COPY INTO)─▶ NOMAD_HUB.RAW.*  ─▶ dbt ─▶ STAGING / MARTS / AI
            NOMAD_WH (XS, auto-suspend 60s, capped by NOMAD_MONITOR)
```

| Done by | What |
|---|---|
| **You, once** (≈20 min) | AWS account + IAM user + CLI profile · Snowflake trial · run one bootstrap SQL block |
| **Terraform** | S3 bucket (encrypted, versioned, private) · IAM role/policy · warehouse + credit cap · database + 5 schemas · 3 roles + grants · 3 service users (key-pair) · storage integration · stage · file format |
| **Scripts** | upload to S3 · create RAW tables · `COPY INTO` |

---

## 0. Prerequisites

| Tool | Check | Install |
|---|---|---|
| AWS CLI v2 | `aws --version` | https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html |
| Terraform ≥ 1.6 | `terraform version` | https://developer.hashicorp.com/terraform/install |
| OpenSSL | `openssl version` | preinstalled on Linux/macOS |
| Python 3.11+ | `python3 --version` | `pip install "snowflake-connector-python>=3.12"` (for `scripts/run_sql.py`) |

The data must already be in `data/raw/` (see the README: `python data/download_sources.py all`
then `python data/generate_data.py`).

**Cost.** S3: ~6 GB ≈ $0.15/month. Snowflake: billed from the $400 trial credit; loading and
transforming the full dataset on an X-Small warehouse uses a few credits. A resource monitor
suspends the warehouse at 50 credits/month (change `monthly_credit_quota`).

**Region.** Use the **same region** for the bucket and the Snowflake account — transfer between
them is then free and loads are faster. This guide uses **`eu-central-1` (Frankfurt)**.

---

## 1. AWS — account, IAM user, CLI profile

1. **Create an AWS account** at https://aws.amazon.com (skip if you have one).
   Turn on MFA for the root user: *IAM → Dashboard → Add MFA*.
2. *(Recommended)* **Budget alert:** *Billing → Budgets → Create budget → "Zero spend" or
   "Monthly cost budget" ($5)* so you get an email if anything starts costing money.
3. **Create an IAM user for Terraform**
   - *IAM → Users → Create user* → name `nomadhub-terraform` → no console access.
   - *Permissions → Attach policies directly → `AdministratorAccess`*.
     (Fine for a personal sandbox. In a company you'd scope this to S3 + IAM role management.)
   - Open the user → *Security credentials → Create access key → Command Line Interface (CLI)*.
     Copy the **Access key ID** and **Secret access key** (shown only once).
4. **Configure a dedicated CLI profile** (keeps this project apart from your other AWS work):

   ```bash
   aws configure --profile nomadhub
   # AWS Access Key ID:     <from step 3>
   # AWS Secret Access Key: <from step 3>
   # Default region name:   eu-central-1
   # Default output format: json

   aws sts get-caller-identity --profile nomadhub     # must print your account ID
   ```

5. **Choose a bucket name.** S3 names are global, so add something personal:
   `nomadhub-<yourname>-raw`. Terraform creates it — don't create it by hand.

---

## 2. Snowflake — trial account

1. Sign up at https://signup.snowflake.com
   - **Edition: Enterprise** (masking and row-access policies in `snowflake/03_security_policies.sql` need it)
   - **Cloud: Amazon Web Services**
   - **Region: Europe Central 1 (Frankfurt)** — same as the bucket
2. Activate the account from the email, set your username/password, log in to **Snowsight**.

You'll need two names from this account; step 4 prints them for you.

---

## 3. Key pairs for the service users

Nothing in this project logs in to Snowflake with a password. Each service user has an RSA
key pair; Snowflake stores only the public half.

```bash
scripts/generate_snowflake_keys.sh
```

This writes four key pairs to `~/.nomadhub/keys/` (outside the repo, `chmod 600`):

| User | Used by | Roles |
|---|---|---|
| `TERRAFORM_SVC` | Terraform | `ACCOUNTADMIN` |
| `AIRFLOW_SVC` | Airflow (load + orchestration) | `LOADER_ROLE`, `DBT_ROLE` |
| `DBT_SVC` | dbt from your laptop | `DBT_ROLE` |
| `STREAMLIT_SVC` | dashboards, text-to-SQL | `ANALYST_ROLE` |

At the end it prints the **TERRAFORM_SVC public key** as one long line — copy it.
The script is safe to re-run; it never overwrites existing keys.

> Keep `~/.nomadhub/keys/` private and backed up. Losing a key is not a disaster: generate a
> new one and re-run `terraform apply` (for TERRAFORM_SVC, re-run step 4 with the new key).

---

## 4. Bootstrap — the only SQL you run by hand

Terraform needs a user to log in with before it can create anything else.

1. In Snowsight: *Projects → Worksheets → + SQL Worksheet*.
2. Paste the contents of [`snowflake/00_bootstrap_terraform.sql`](snowflake/00_bootstrap_terraform.sql).
3. Replace `<PASTE_TERRAFORM_SVC_PUBLIC_KEY_HERE>` with the key from step 3 (keep the quotes).
4. *Run All* (Ctrl/Cmd + Shift + Enter).

The last query returns the values for step 5:

| Column | Goes into `terraform.tfvars` as |
|---|---|
| `SNOWFLAKE_ORGANIZATION_NAME` | `snowflake_organization_name` |
| `SNOWFLAKE_ACCOUNT_NAME` | `snowflake_account_name` |
| `SNOWFLAKE_HUMAN_USER` | `snowflake_human_user` (your login; gets the project roles) |

Your account identifier is `ORGNAME-ACCOUNTNAME` — that's what connectors call `SNOWFLAKE_ACCOUNT`.

---

## 5. Terraform — create everything

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars    # then edit: bucket name + values from step 4
terraform init
terraform plan                                  # review: ~60 resources to add, 0 to change/destroy
terraform apply                                 # type "yes"
```

`apply` takes about a minute. What it does, in order:

1. Creates the S3 bucket with encryption, versioning, public access blocked, and a lifecycle rule.
2. Creates the Snowflake warehouse, resource monitor, `NOMAD_HUB` database and schemas
   `RAW`, `STAGING`, `MARTS`, `SNAPSHOTS`, `AI`.
3. Creates `LOADER_ROLE`, `DBT_ROLE`, `ANALYST_ROLE`, their grants (including *future* grants,
   so tables created later are readable by the right roles), and the three service users.
4. **The handshake.** Creates the storage integration `NOMAD_S3_INT` pointing at the IAM role's
   ARN, reads Snowflake's generated IAM user + external ID from it, and puts both into the
   role's trust policy. By hand this is the "create role → create integration →
   `DESC INTEGRATION` → edit trust policy" back-and-forth; here it's one apply.
5. Creates the external stage `NOMAD_HUB.RAW.RAW_STAGE` → `s3://<bucket>/raw/` with the
   `CSV_GZ` file format.

Check the outputs:

```bash
terraform output
```

The state file (`terraform.tfstate`) stays on your machine and is gitignored. Don't delete it —
it's how Terraform knows what it created.

---

## 6. Upload the data lake

```bash
scripts/upload_raw.sh          # reads the bucket from `terraform output`
```

This runs `aws s3 sync data/raw/ s3://<bucket>/raw/`: ~1,200 files, ~6 GB. How long it
takes depends on your upload speed (≈15 min at 50 Mbit/s). Re-running uploads only new or
changed files.

Check from Snowflake that the stage sees the files (Snowsight worksheet):

```sql
USE ROLE LOADER_ROLE;
LIST @NOMAD_HUB.RAW.RAW_STAGE/flights/ PATTERN = '.*2025.*';   -- should list 12 monthly files
```

---

## 7. Create the RAW tables and load them

```bash
export SNOWFLAKE_ACCOUNT=$(terraform -chdir=terraform output -raw snowflake_account)
python scripts/run_sql.py snowflake/01_raw_tables.sql      # 10 tables, all VARCHAR + lineage columns
python scripts/run_sql.py snowflake/02_copy_into.sql       # COPY INTO from the stage
```

You can also paste both files into a Snowsight worksheet instead.

`02_copy_into.sql` ends with a row-count query. Compare it with `data/raw/_manifest.json`:

| Table | Rows |
|---|---|
| calendar | 188,305,705 |
| flights | 45,763,492 |
| reviews | 22,061,371 |
| stay_bookings | 17,890,064 |
| users | 12,628,359 |
| flight_bookings | 6,884,692 |
| listings | 514,296 |
| airports | 86,153 |
| regions | 3,987 |
| countries | 249 |

Each RAW row carries `_SOURCE_FILE` (the S3 key it came from) and `_LOADED_AT`.

**Re-running is safe.** `COPY INTO` keeps 64 days of load history per table and skips files it
has already loaded, so the next run (e.g. the daily Airflow DAG) loads only new files.

---

## 8. Day-to-day

| Task | Command |
|---|---|
| Pause compute | nothing — `NOMAD_WH` auto-suspends after 60 s idle |
| See credit usage | Snowsight → *Admin → Cost Management*, or `SHOW RESOURCE MONITORS;` |
| New data (new BTS month, new Airbnb snapshot) | `python data/download_sources.py all` → `scripts/upload_raw.sh` → `python scripts/run_sql.py snowflake/02_copy_into.sql` |
| Change infra (e.g. warehouse size) | edit `terraform/*.tf` → `terraform plan` → `terraform apply` |

## 9. Tear down

```bash
cd terraform && terraform destroy
```

This deletes the bucket **including its objects** (`force_destroy = true` — the data is
reproducible from `data/raw/`), the IAM role, and every Snowflake object Terraform created.
Then, in Snowsight, remove the bootstrap user: `DROP USER TERRAFORM_SVC;`.
Your local `data/raw/` and `~/.nomadhub/keys/` are untouched.

---

## Troubleshooting

| Symptom | Cause → fix |
|---|---|
| `terraform plan`: *JWT token is invalid* | The public key in step 4 doesn't match `~/.nomadhub/keys/terraform_svc_rsa_key.p8`, or org/account names are wrong. Re-run the last query of the bootstrap SQL and compare. |
| `terraform plan`: *NoCredentialProviders* / *profile not found* | AWS profile missing: `aws configure --profile nomadhub`, or set `aws_profile` in `terraform.tfvars`. |
| `apply`: *BucketAlreadyExists* | Bucket names are global — choose another `bucket_name`. |
| `LIST @RAW_STAGE`: *Access Denied* / *not authorized to perform sts:AssumeRole* | IAM changes can take ~1 min to propagate; retry. If it persists, run `terraform apply` again — it re-syncs the trust policy with the integration. Never `CREATE OR REPLACE` the integration by hand: that generates a new external ID and breaks the trust. |
| `COPY`: *Number of columns in file does not match* | A file in that folder has a different layout. All files of one table must share the header that `01_raw_tables.sql` was generated from. |
| `COPY` loads 0 rows | Files were already loaded (load history), or `upload_raw.sh` hasn't run. `LIST @NOMAD_HUB.RAW.RAW_STAGE/<table>/;` |
| Warehouse suspended unexpectedly | The resource monitor hit its quota. `SHOW RESOURCE MONITORS;` — raise `monthly_credit_quota` and `terraform apply`. |

## Security notes

- **No long-lived cloud keys in Snowflake.** S3 access works by Snowflake assuming an IAM role,
  restricted to `s3://<bucket>/raw/*` and to your integration's external ID.
- **No passwords for services.** All service users are `TYPE = SERVICE` with key-pair auth;
  private keys live outside the repo.
- **Least privilege.** Loaders can only write RAW; dbt can only read RAW and write the
  modelled layers; analysts are read-only. All roles roll up to `SYSADMIN`.
- **Cost guardrail.** `NOMAD_MONITOR` notifies at 50 % / 80 % and suspends the warehouse at 100 %.
- **Simplification for a personal account:** Terraform itself runs as `ACCOUNTADMIN`. In a team
  you'd give it a custom role with only `CREATE DATABASE/WAREHOUSE/INTEGRATION/ROLE/USER`.
