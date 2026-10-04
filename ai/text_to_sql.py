"""
Text-to-SQL — "ask the warehouse in plain English"
==================================================
1. Reads the live schema of the MARTS and AI tables (names, types, comments) from
   INFORMATION_SCHEMA, so the prompt never drifts from what dbt actually built.
2. Gemini writes ONE Snowflake SELECT for the question.
3. A guard rejects anything that isn't a single read-only query.
4. The query runs as STREAMLIT_SVC / ANALYST_ROLE, which can only SELECT — the guard is a
   courtesy; the role is the real security boundary. At most 500 rows are fetched.

  python ai/text_to_sql.py "Which airline had the worst on-time rate in 2025?"

The Streamlit app imports generate_sql(), is_safe() and run().
"""

import argparse
import re

import pandas as pd
from google.genai import types
from pydantic import BaseModel

from common import GEMINI_MODEL, gemini, reader_connection

MAX_ROWS = 500
FORBIDDEN = re.compile(
    r"\b(insert|update|delete|merge|drop|create|alter|truncate|grant|revoke|copy|put|get|"
    r"call|execute|undrop|use|set|unset|commit|rollback|begin|remove|list)\b",
    re.IGNORECASE,
)

SCHEMA_SQL = """
SELECT table_schema, table_name, column_name, data_type, comment
FROM NOMAD_HUB.INFORMATION_SCHEMA.COLUMNS
WHERE table_schema IN ('MARTS', 'AI')
  AND table_name NOT LIKE '%%EMBEDDINGS%%'
ORDER BY table_schema, table_name, ordinal_position
"""

GUIDE = """
Business notes:
- mart_* tables are pre-aggregated; prefer them over the fct_* tables when they fit.
- Money is USD in *_usd columns. platform_revenue_usd = NomadHub's service fees.
- on_time_rate excludes cancelled/diverted flights (DOT definition).
- Flights are US domestic only (BTS). Stays cover 20 cities (10 US, 10 international).
- City values are lowercase keys like 'new_york', 'paris', 'tokyo'.
"""


class SqlAnswer(BaseModel):
    sql: str
    explanation: str


def schema_description(conn) -> str:
    lines, current = [], None
    for schema, table, column, dtype, comment in conn.cursor().execute(SCHEMA_SQL).fetchall():
        if (schema, table) != current:
            current = (schema, table)
            lines.append(f"\n{schema}.{table}:")
        lines.append(f"  {column} {dtype}" + (f" -- {comment}" if comment else ""))
    return "\n".join(lines)


def generate_sql(question: str, schema: str) -> SqlAnswer:
    response = gemini().models.generate_content(
        model=GEMINI_MODEL,
        contents=question,
        config=types.GenerateContentConfig(
            temperature=0,
            response_mime_type="application/json",
            response_schema=SqlAnswer,
            system_instruction=(
                "You write ONE Snowflake SQL SELECT statement (CTEs allowed) that answers the "
                "question using only these tables. Always qualify tables as NOMAD_HUB.<schema>.<table>. "
                "Never modify data. Return the SQL and a one-sentence explanation.\n"
                f"{GUIDE}\nTables:{schema}"
            ),
        ),
    )
    return response.parsed


def is_safe(sql: str) -> tuple[bool, str]:
    body = sql.strip().rstrip(";").strip()
    without_strings = re.sub(r"'(?:[^']|'')*'", "''", body)
    if ";" in without_strings:
        return False, "Only a single statement is allowed."
    if not re.match(r"^(select|with)\b", without_strings, re.IGNORECASE):
        return False, "Only SELECT queries are allowed."
    match = FORBIDDEN.search(without_strings)
    if match:
        return False, f"Keyword not allowed: {match.group(0).upper()}"
    return True, body


def run(sql: str, conn) -> pd.DataFrame:
    cur = conn.cursor()
    cur.execute("ALTER SESSION SET STATEMENT_TIMEOUT_IN_SECONDS = 60")
    # Cap rows at fetch time: wrapping the query in SELECT * FROM (...) LIMIT n would let
    # Snowflake drop the inner ORDER BY, silently returning the wrong "top" rows.
    cur.execute(sql)
    rows = cur.fetchmany(MAX_ROWS)
    return pd.DataFrame(rows, columns=[c[0] for c in cur.description])


def main() -> None:
    parser = argparse.ArgumentParser(description="Ask the NomadHub warehouse in plain English")
    parser.add_argument("question")
    args = parser.parse_args()

    conn = reader_connection()
    result = generate_sql(args.question, schema_description(conn))
    print(f"-- {result.explanation}\n{result.sql}\n")
    ok, sql_or_reason = is_safe(result.sql)
    if not ok:
        raise SystemExit(f"Rejected: {sql_or_reason}")
    with pd.option_context("display.width", 160, "display.max_columns", 12):
        print(run(sql_or_reason, conn).head(20))
    conn.close()


if __name__ == "__main__":
    main()
