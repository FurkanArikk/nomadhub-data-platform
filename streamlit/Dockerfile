FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies for Streamlit & AI
RUN pip install --no-cache-dir \
    streamlit==1.38.0 \
    plotly==5.24.1 \
    pandas==2.2.2 \
    numpy==1.26.4 \
    faiss-cpu==1.8.0.post1 \
    duckdb==1.0.0 \
    snowflake-connector-python==3.12.3 \
    google-generativeai==0.7.0 \
    python-dotenv==1.0.1

EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

ENTRYPOINT ["streamlit", "run", "streamlit/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
