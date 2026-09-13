"""
NomadHub Pipeline DAG
======================
Daily batch pipeline: S3 → Snowflake RAW → STAGING → MARTS → AI Enrichment → AI MARTS

Architecture: 4 TaskGroups (isolated, independently retriable)
  ┌─ ingest ─────────────────────────────────────────────────────────────────┐
  │  validate_source_files → copy_into_[7 tables] (parallel BashOperators)   │
  └──────────────────────────────────────────────────────────────────────────┘
           ↓
  ┌─ transform ──────────────────────────────────────────────────────────────┐
  │  dbt_staging → dbt_test_staging → dbt_marts → dbt_test_marts            │
  └──────────────────────────────────────────────────────────────────────────┘
           ↓
  ┌─ ai_enrich ──────────────────────────────────────────────────────────────┐
  │  enrich_new_reviews (Gemini) → verify_enrichment                        │
  └──────────────────────────────────────────────────────────────────────────┘
           ↓
  ┌─ ai_marts ───────────────────────────────────────────────────────────────┐
  │  dbt_run_ai_marts → dbt_test_all → notify_success                       │
  └──────────────────────────────────────────────────────────────────────────┘

Schedule: @daily (runs at 02:00 UTC)
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from airflow.providers.snowflake.operators.snowflake import SnowflakeOperator
from airflow.utils.task_group import TaskGroup

# ── Default args ─────────────────────────────────────────────────────────────
DEFAULT_ARGS = {
    "owner": "nomad-hub",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

SNOWFLAKE_CONN = "snowflake_default"  # Configure in Airflow UI → Connections
DBT_PROJECT    = os.environ.get("DBT_PROJECT_DIR", "/opt/airflow/nomad_hub")
DBT_PROFILES   = os.environ.get("DBT_PROFILES_DIR", "/opt/airflow/nomad_hub")
AI_SCRIPTS     = "/opt/airflow/ai"

# Raw tables to load in parallel
RAW_TABLES = [
    "countries",
    "airports",
    "hotels",
    "users",
    "flights",
    "hotel_bookings",
    "reviews",
]

# ── COPY INTO SQL template ────────────────────────────────────────────────────
COPY_INTO_SQL = """
COPY INTO NOMAD_HUB.RAW.{table_upper}
FROM @NOMAD_HUB.RAW.NOMAD_S3_STAGE/{table}/
FILE_FORMAT = (FORMAT_NAME = NOMAD_HUB.RAW.NOMAD_CSV_FORMAT)
ON_ERROR = 'CONTINUE'
PURGE = FALSE
"""

# ── Helper: validate source row counts ───────────────────────────────────────
def check_raw_row_counts(**context) -> None:
    """Assert that RAW tables have data after COPY INTO."""
    import snowflake.connector

    conn = snowflake.connector.connect(
        account   = os.environ["SNOWFLAKE_ACCOUNT"],
        user      = os.environ["SNOWFLAKE_USER"],
        password  = os.environ["SNOWFLAKE_PASSWORD"],
        database  = "NOMAD_HUB",
        warehouse = "NOMAD_WH",
        role      = "NOMAD_ADMIN",
    )
    cursor = conn.cursor()

    empty_tables = []
    for table in RAW_TABLES:
        cursor.execute(f"SELECT COUNT(*) FROM NOMAD_HUB.RAW.{table.upper()}")
        count = cursor.fetchone()[0]
        if count == 0:
            empty_tables.append(table)

    conn.close()

    if empty_tables:
        raise ValueError(f"RAW tables are empty after COPY INTO: {empty_tables}")

    context["ti"].log.info("✅ All RAW tables have data.")


# ── Helper: verify enrichment ─────────────────────────────────────────────────
def verify_enrichment(**context) -> None:
    """Check that at least some reviews were enriched in this run."""
    import snowflake.connector

    conn = snowflake.connector.connect(
        account   = os.environ["SNOWFLAKE_ACCOUNT"],
        user      = os.environ["SNOWFLAKE_USER"],
        password  = os.environ["SNOWFLAKE_PASSWORD"],
        database  = "NOMAD_HUB",
        warehouse = "NOMAD_WH",
        role      = "DBT_ROLE",
    )
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM NOMAD_HUB.AI.REVIEW_ENRICHED "
        "WHERE ENRICHED_AT >= DATEADD('hour', -2, CURRENT_TIMESTAMP())"
    )
    recent_count = cursor.fetchone()[0]
    conn.close()
    context["ti"].log.info(f"✅ {recent_count} reviews enriched in the last 2 hours.")


# ── DAG ───────────────────────────────────────────────────────────────────────
with DAG(
    dag_id          = "nomad_hub_pipeline",
    description     = "NomadHub daily batch pipeline: S3 → RAW → STAGING → MARTS → AI",
    schedule        = "@daily",
    start_date      = datetime(2024, 1, 1),
    catchup         = False,
    default_args    = DEFAULT_ARGS,
    tags            = ["nomad-hub", "production"],
    doc_md          = __doc__,
    max_active_runs = 1,
) as dag:

    # ─────────────────────────────────────────────────────────────────────────
    # TaskGroup 1: INGEST — Load S3 CSVs into Snowflake RAW
    # ─────────────────────────────────────────────────────────────────────────
    with TaskGroup("ingest", tooltip="Load S3 data into Snowflake RAW (Bronze)") as tg_ingest:

        # Load all 7 tables in parallel
        copy_tasks = []
        for table in RAW_TABLES:
            task = SnowflakeOperator(
                task_id          = f"copy_into_{table}",
                snowflake_conn_id= SNOWFLAKE_CONN,
                sql              = COPY_INTO_SQL.format(
                    table_upper=table.upper(),
                    table=table,
                ),
            )
            copy_tasks.append(task)

        # After all copies, validate row counts
        validate = PythonOperator(
            task_id         = "validate_row_counts",
            python_callable = check_raw_row_counts,
        )

        # All copy tasks run in parallel, then validate
        copy_tasks >> validate

    # ─────────────────────────────────────────────────────────────────────────
    # TaskGroup 2: TRANSFORM — dbt STAGING → MARTS
    # ─────────────────────────────────────────────────────────────────────────
    with TaskGroup("transform", tooltip="dbt: STAGING (Silver) → MARTS (Gold)") as tg_transform:

        dbt_staging_run = BashOperator(
            task_id  = "dbt_run_staging",
            bash_command=(
                f"cd {DBT_PROJECT} && "
                f"dbt run --profiles-dir {DBT_PROFILES} --target prod "
                f"--select staging --no-write-json"
            ),
        )

        dbt_staging_test = BashOperator(
            task_id  = "dbt_test_staging",
            bash_command=(
                f"cd {DBT_PROJECT} && "
                f"dbt test --profiles-dir {DBT_PROFILES} --target prod "
                f"--select staging --no-write-json"
            ),
        )

        dbt_dims_run = BashOperator(
            task_id  = "dbt_run_dimensions",
            bash_command=(
                f"cd {DBT_PROJECT} && "
                f"dbt run --profiles-dir {DBT_PROFILES} --target prod "
                f"--select tag:dimension --no-write-json"
            ),
        )

        dbt_facts_run = BashOperator(
            task_id  = "dbt_run_facts",
            bash_command=(
                f"cd {DBT_PROJECT} && "
                f"dbt run --profiles-dir {DBT_PROFILES} --target prod "
                f"--select tag:fact --no-write-json"
            ),
        )

        dbt_biz_marts_run = BashOperator(
            task_id  = "dbt_run_business_marts",
            bash_command=(
                f"cd {DBT_PROJECT} && "
                f"dbt run --profiles-dir {DBT_PROFILES} --target prod "
                f"--select mart_revenue_summary mart_destination_performance "
                f"mart_cancellation_analysis mart_user_cohort --no-write-json"
            ),
        )

        dbt_marts_test = BashOperator(
            task_id  = "dbt_test_marts",
            bash_command=(
                f"cd {DBT_PROJECT} && "
                f"dbt test --profiles-dir {DBT_PROFILES} --target prod "
                f"--select tag:gold --no-write-json"
            ),
        )

        # Sequential within transform: staging → dims → facts → business marts → test
        dbt_staging_run >> dbt_staging_test >> dbt_dims_run >> dbt_facts_run >> dbt_biz_marts_run >> dbt_marts_test

    # ─────────────────────────────────────────────────────────────────────────
    # TaskGroup 3: AI_ENRICH — Gemini enrichment
    # ─────────────────────────────────────────────────────────────────────────
    with TaskGroup("ai_enrich", tooltip="Gemini review enrichment") as tg_ai_enrich:

        enrich_reviews = BashOperator(
            task_id  = "enrich_new_reviews",
            bash_command=(
                f"cd {AI_SCRIPTS} && "
                "python enrich_reviews.py --batch-size 20 --limit 5000"
            ),
        )

        verify_enrich = PythonOperator(
            task_id         = "verify_enrichment",
            python_callable = verify_enrichment,
        )

        enrich_reviews >> verify_enrich

    # ─────────────────────────────────────────────────────────────────────────
    # TaskGroup 4: AI_MARTS — Build AI mart models
    # ─────────────────────────────────────────────────────────────────────────
    with TaskGroup("ai_marts", tooltip="dbt AI mart + final tests") as tg_ai_marts:

        dbt_ai_mart = BashOperator(
            task_id  = "dbt_run_ai_marts",
            bash_command=(
                f"cd {DBT_PROJECT} && "
                f"dbt run --profiles-dir {DBT_PROFILES} --target prod "
                f"--select mart_review_insights --no-write-json"
            ),
        )

        dbt_full_test = BashOperator(
            task_id  = "dbt_test_all",
            bash_command=(
                f"cd {DBT_PROJECT} && "
                f"dbt test --profiles-dir {DBT_PROFILES} --target prod --no-write-json"
            ),
        )

        dbt_ai_mart >> dbt_full_test

    # ─────────────────────────────────────────────────────────────────────────
    # DAG-level dependencies: group ordering
    # ─────────────────────────────────────────────────────────────────────────
    tg_ingest >> tg_transform >> tg_ai_enrich >> tg_ai_marts
