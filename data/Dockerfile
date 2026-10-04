FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies for Data generation & AWS S3 ingestion
RUN pip install --no-cache-dir \
    faker==28.4.1 \
    pandas==2.2.2 \
    numpy==1.26.4 \
    tqdm==4.66.5 \
    boto3==1.35.0 \
    requests==2.32.3 \
    duckdb==1.5.6 \
    python-dotenv==1.0.1

ENTRYPOINT ["python"]
CMD ["data/generate_data.py"]
