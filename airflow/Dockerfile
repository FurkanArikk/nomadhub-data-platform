FROM apache/airflow:3.0.0-python3.11

USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

USER airflow

# Install providers and dependencies
RUN pip install --no-cache-dir \
    apache-airflow-providers-snowflake==5.3.0 \
    apache-airflow-providers-amazon==8.25.0 \
    apache-airflow-providers-http==4.12.0 \
    snowflake-connector-python==3.12.3 \
    boto3==1.34.0 \
    google-generativeai==0.7.0 \
    python-dotenv==1.0.0 \
    pandas==2.2.0 \
    dbt-snowflake==1.8.0
