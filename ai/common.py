"""
Shared plumbing for the AI layer: settings, Snowflake connection (key-pair), Gemini client.

Settings come from the environment, falling back to the repo-root .env:
  GEMINI_API_KEY                 required
  GEMINI_MODEL                   text model for RAG answers and text-to-SQL
  GEMINI_ENRICH_MODEL            cheaper/faster model for bulk review enrichment
  GEMINI_EMBED_MODEL             embedding model for RAG (must return one vector per input)
  SNOWFLAKE_ACCOUNT              ORGNAME-ACCOUNTNAME
  SNOWFLAKE_KEY_DIR              default ~/.nomadhub/keys
"""

import logging
import os
from functools import lru_cache
from pathlib import Path

import snowflake.connector
from dotenv import load_dotenv
from google import genai

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# Pinned, non-preview models verified against the live model list (2026-10).
# gemini-embedding-2 is NOT used: it merges a list of texts into one embedding.
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
GEMINI_ENRICH_MODEL = os.getenv("GEMINI_ENRICH_MODEL", "gemini-3.5-flash-lite")
GEMINI_EMBED_MODEL = os.getenv("GEMINI_EMBED_MODEL", "gemini-embedding-001")

# The SDK warns about automatic function calling on every call; we don't use tools.
logging.getLogger("google_genai.models").setLevel(logging.ERROR)
EMBED_DIM = 768  # Matryoshka-truncated embedding size; must match the VECTOR column

DATABASE = "NOMAD_HUB"
WAREHOUSE = "NOMAD_WH"


def snowflake_connection(user: str, role: str, schema: str = "AI"):
    """Key-pair connection as one of the service users (see CLOUD.md)."""
    key_dir = Path(os.getenv("SNOWFLAKE_KEY_DIR", "~/.nomadhub/keys")).expanduser()
    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=user,
        authenticator="SNOWFLAKE_JWT",
        private_key_file=str(key_dir / f"{user.lower()}_rsa_key.p8"),
        role=role,
        warehouse=WAREHOUSE,
        database=DATABASE,
        schema=schema,
        session_parameters={"QUERY_TAG": "nomadhub-ai"},
    )


def writer_connection():
    """Writes to the AI schema (DBT_ROLE). Airflow sets AI_SNOWFLAKE_USER=AIRFLOW_SVC."""
    return snowflake_connection(os.getenv("AI_SNOWFLAKE_USER", "DBT_SVC"), "DBT_ROLE")


def reader_connection(schema: str = "MARTS"):
    """Read-only access (ANALYST_ROLE) for RAG search and text-to-SQL."""
    return snowflake_connection(os.getenv("APP_SNOWFLAKE_USER", "STREAMLIT_SVC"), "ANALYST_ROLE", schema)


@lru_cache(maxsize=1)
def gemini() -> genai.Client:
    key = os.getenv("GEMINI_API_KEY", "")
    if not key or key == "AIzaSyYourGeminiApiKeyHere":
        raise SystemExit("GEMINI_API_KEY is not set — create one at https://aistudio.google.com/apikey "
                         "and put it in .env")
    return genai.Client(api_key=key)
