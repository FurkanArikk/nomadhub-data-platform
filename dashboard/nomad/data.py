"""
Read-only data access for the dashboard.

Everything runs as STREAMLIT_SVC / ANALYST_ROLE (SELECT only), through the same
key-pair connection the AI scripts use. Query results are cached for an hour, so
page switches don't re-hit the warehouse.
"""

import sys
from decimal import Decimal
from pathlib import Path

import pandas as pd
import snowflake.connector
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ai"))

from common import reader_connection  # noqa: E402  (needs the sys.path entry above)


def numeric(df: pd.DataFrame) -> pd.DataFrame:
    """Snowflake returns NUMBER(p, s) aggregates as Python Decimal objects; make them floats."""
    for col in df.select_dtypes(include="object").columns:
        sample = df[col].dropna()
        if len(sample) and isinstance(sample.iloc[0], Decimal):
            df[col] = df[col].astype(float)
    return df


@st.cache_resource(show_spinner=False)
def connection():
    return reader_connection("MARTS")


@st.cache_data(ttl=3600, show_spinner="Querying Snowflake…")
def query(sql: str, params: tuple = ()) -> pd.DataFrame:
    try:
        cur = connection().cursor()
        cur.execute(sql, params)
    except snowflake.connector.errors.Error:
        connection.clear()               # session expired: reconnect once
        cur = connection().cursor()
        cur.execute(sql, params)
    df = cur.fetch_pandas_all()
    df.columns = [c.lower() for c in df.columns]
    return numeric(df)
