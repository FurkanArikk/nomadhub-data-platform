# NomadHub dashboard. Build context = repo root (see docker-compose.yaml):
# it needs dashboard/ plus the AI layer in ai/ (RAG + text-to-SQL).
FROM python:3.12-slim

WORKDIR /app
RUN pip install --no-cache-dir \
      "streamlit~=1.65" \
      "plotly>=6" \
      "pandas>=2.2" \
      "google-genai>=2.28" \
      "snowflake-connector-python[pandas]>=3.12" \
      "python-dotenv>=1.0" \
      "pydantic>=2.7"

COPY .streamlit/ .streamlit/
COPY ai/ ai/
COPY dashboard/ dashboard/

EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')"
CMD ["streamlit", "run", "dashboard/app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
