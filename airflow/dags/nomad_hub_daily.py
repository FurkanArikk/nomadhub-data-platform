"""
NomadHub daily pipeline
=======================
    ingest      COPY INTO RAW from the S3 stage (only files not loaded before)
       ↓
    transform   dbt build — staging, dimensions, incremental facts, marts, snapshot, tests
       ↓
    ai          Gemini enrichment of new reviews → embed new reviews for RAG → dbt build tag:ai

Every step is incremental and idempotent, so a daily run only does the new work:
COPY skips files already loaded, the facts MERGE on rows with a newer _loaded_at,
and the AI jobs pick only reviews they haven't processed yet.

Credentials never appear here: Snowflake auth is key-pair (keys mounted read-only at
/opt/airflow/keys), the connection comes from AIRFLOW_CONN_SNOWFLAKE_DEFAULT, and the
Gemini key from the environment.
"""

from datetime import datetime, timedelta

from airflow.providers.common.sql.operators.sql import SQLExecuteQueryOperator
from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG, Param, TaskGroup

DBT = "/opt/airflow/venvs/dbt/bin/dbt"
PYTHON_AI = "/opt/airflow/venvs/ai/bin/python"
DBT_PROJECT = "/opt/airflow/nomad_hub"
AI_DIR = "/opt/airflow/ai"

# dbt writes target/ and logs/ to /tmp so container runs never clobber a developer's
# local artefacts in the mounted project folder. Set via env vars, which every dbt
# command honours (dbt deps doesn't accept --target-path).
DBT_FLAGS = "--profiles-dir ."
DBT_ENV = {"DBT_TARGET_PATH": "/tmp/dbt/target", "DBT_LOG_PATH": "/tmp/dbt/logs"}

with DAG(
    dag_id="nomad_hub_daily",
    description="S3 → RAW → dbt → Gemini enrichment + RAG index → AI marts",
    schedule="@daily",
    start_date=datetime(2026, 10, 1),
    catchup=False,
    max_active_runs=1,
    template_searchpath=["/opt/airflow/sql"],
    default_args={"retries": 1, "retry_delay": timedelta(minutes=5)},
    params={
        "enrich_limit": Param(500, type="integer", minimum=0, description="new reviews to enrich"),
        "embed_limit": Param(2000, type="integer", minimum=0, description="new reviews to embed"),
    },
    tags=["nomadhub", "snowflake", "dbt", "gemini"],
    doc_md=__doc__,
) as dag:

    with TaskGroup("ingest", tooltip="S3 → Snowflake RAW (Bronze)") as ingest:
        copy_into_raw = SQLExecuteQueryOperator(
            task_id="copy_into_raw",
            conn_id="snowflake_default",
            sql="02_copy_into.sql",          # snowflake/02_copy_into.sql, mounted at /opt/airflow/sql
            split_statements=True,
            return_last=True,                # the final statement is the row-count check
            show_return_value_in_logs=True,
        )

    with TaskGroup("transform", tooltip="dbt: STAGING (Silver) → MARTS (Gold)") as transform:
        dbt_deps = BashOperator(
            task_id="dbt_deps",
            env=DBT_ENV,
            append_env=True,
            bash_command=f"cd {DBT_PROJECT} && {DBT} deps {DBT_FLAGS}",
        )
        dbt_build_core = BashOperator(
            task_id="dbt_build_core",
            env=DBT_ENV,
            append_env=True,
            bash_command=f"cd {DBT_PROJECT} && {DBT} build --exclude tag:ai {DBT_FLAGS}",
        )
        dbt_deps >> dbt_build_core

    with TaskGroup("ai", tooltip="Gemini enrichment, RAG index, AI marts") as ai:
        enrich_reviews = BashOperator(
            task_id="enrich_reviews",
            bash_command=f"cd {AI_DIR} && {PYTHON_AI} enrich_reviews.py --limit {{{{ params.enrich_limit }}}}",
        )
        embed_reviews = BashOperator(
            task_id="embed_reviews",
            bash_command=f"cd {AI_DIR} && {PYTHON_AI} rag.py index --limit {{{{ params.embed_limit }}}}",
        )
        dbt_build_ai = BashOperator(
            task_id="dbt_build_ai",
            env=DBT_ENV,
            append_env=True,
            bash_command=f"cd {DBT_PROJECT} && {DBT} build --select tag:ai {DBT_FLAGS}",
        )
        # enrichment first: the RAG index prefers already-enriched reviews
        enrich_reviews >> embed_reviews >> dbt_build_ai

    ingest >> transform >> ai
