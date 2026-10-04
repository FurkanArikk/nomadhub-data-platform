# Airflow 3 + the NomadHub job runtimes.
# dbt and the AI scripts each get their own virtualenv, so their dependency trees can
# never clash with Airflow's (or each other's). Tasks call them by absolute path.
ARG AIRFLOW_VERSION=3.3.2
ARG PYTHON_VERSION=3.12
FROM apache/airflow:${AIRFLOW_VERSION}-python${PYTHON_VERSION}

ARG AIRFLOW_VERSION=3.3.2
ARG PYTHON_VERSION=3.12

# Providers, pinned by Airflow's own constraints file:
#   snowflake  → SQLExecuteQueryOperator connection (COPY INTO)
#   fab        → classic username/password login for the UI
RUN pip install --no-cache-dir \
      "apache-airflow==${AIRFLOW_VERSION}" \
      apache-airflow-providers-snowflake \
      apache-airflow-providers-fab \
      --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PYTHON_VERSION}.txt"

RUN python -m venv /opt/airflow/venvs/dbt \
 && /opt/airflow/venvs/dbt/bin/pip install --no-cache-dir "dbt-snowflake~=1.12.0"

RUN python -m venv /opt/airflow/venvs/ai \
 && /opt/airflow/venvs/ai/bin/pip install --no-cache-dir \
      "google-genai>=2.28" \
      "snowflake-connector-python[pandas]>=3.12" \
      "python-dotenv>=1.0" \
      "pydantic>=2.7"
