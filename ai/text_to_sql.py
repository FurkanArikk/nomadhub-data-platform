"""
NomadHub — Text-to-SQL: "Query Your Warehouse in Plain English"
================================================================
Fetches MARTS schema metadata from Snowflake,
sends NL questions to Gemini 1.5 Flash for SQL generation,
executes the SQL (SELECT-only, using DBT_ROLE),
and displays results.

Security:
  - Only SELECT statements are allowed (ANALYST_ROLE = read-only)
  - SQL is validated before execution
  - Schema context is injected as Gemini system prompt

Run: streamlit run text_to_sql.py
"""

import os
import re

import pandas as pd
import snowflake.connector
import streamlit as st
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

genai.configure(api_key=os.environ["GEMINI_API_KEY"])
CHAT_MODEL = genai.GenerativeModel("gemini-1.5-flash")

MAX_ROWS = 500  # Safety limit for query results


# ── Snowflake ─────────────────────────────────────────────────────────────────
@st.cache_resource
def get_conn():
    return snowflake.connector.connect(
        account   = os.environ["SNOWFLAKE_ACCOUNT"],
        user      = os.environ["SNOWFLAKE_USER"],
        password  = os.environ["SNOWFLAKE_PASSWORD"],
        database  = "NOMAD_HUB",
        schema    = "MARTS",
        warehouse = "NOMAD_WH",
        role      = "ANALYST_ROLE",  # Read-only role
    )


@st.cache_data(ttl=1800, show_spinner="Loading schema metadata...")
def get_schema_context() -> str:
    """Build a compact schema description for the LLM prompt."""
    conn = get_conn()
    cursor = conn.cursor()

    schema_parts = []

    # Get all tables in MARTS + AI schemas
    for schema in ("MARTS", "AI"):
        try:
            cursor.execute(f"SHOW TABLES IN SCHEMA NOMAD_HUB.{schema}")
            tables = cursor.fetchall()
        except Exception:
            continue

        for table_row in tables:
            table_name = table_row[1]
            full_name = f"NOMAD_HUB.{schema}.{table_name}"
            try:
                cursor.execute(f"DESCRIBE TABLE {full_name}")
                cols = cursor.fetchall()
                col_defs = ", ".join(f"{c[0]} ({c[1]})" for c in cols[:20])
                schema_parts.append(f"  Table: {schema}.{table_name}\n  Columns: {col_defs}")
            except Exception:
                pass

    return "\n\n".join(schema_parts)


# ── SQL Safety Guard ──────────────────────────────────────────────────────────

def validate_sql(sql: str) -> tuple[bool, str]:
    """
    Validate that the SQL is a safe SELECT statement.
    Returns (is_safe, cleaned_sql_or_error).
    """
    # Strip markdown code fences
    sql = re.sub(r"```(?:sql)?", "", sql, flags=re.IGNORECASE).strip("`").strip()

    # Check it's a SELECT
    first_keyword = sql.strip().split()[0].upper()
    if first_keyword != "SELECT":
        return False, f"Only SELECT statements are allowed. Got: {first_keyword}"

    # Block dangerous keywords
    dangerous = ["INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER",
                 "TRUNCATE", "MERGE", "EXECUTE", "EXEC", "CALL", "GRANT", "REVOKE"]
    sql_upper = sql.upper()
    for kw in dangerous:
        if re.search(rf"\b{kw}\b", sql_upper):
            return False, f"Statement contains disallowed keyword: {kw}"

    # Inject row limit if not present
    if "LIMIT" not in sql_upper:
        sql = f"{sql.rstrip(';')}\nLIMIT {MAX_ROWS}"

    return True, sql


# ── SQL Generation ─────────────────────────────────────────────────────────────

SQL_SYSTEM_PROMPT = """You are an expert Snowflake SQL analyst for NomadHub, a travel booking platform.

Database: NOMAD_HUB
Available schemas: MARTS (Gold layer), AI (AI enrichment layer)

Schema context:
{schema}

Rules:
1. Generate ONLY valid Snowflake SQL SELECT statements.
2. Use fully-qualified table names: NOMAD_HUB.MARTS.<table> or NOMAD_HUB.AI.<table>
3. Do NOT use backticks; use double quotes for identifiers if needed.
4. Do NOT add LIMIT — it will be added automatically.
5. Return ONLY the SQL, no explanations, no markdown.
6. Use appropriate aggregations and GROUP BY for analytical questions.
7. For time-series: use DATE_TRUNC and join with DIM_DATE when useful.

User question: {question}

SQL:"""


def generate_sql(question: str, schema_context: str) -> str:
    prompt = SQL_SYSTEM_PROMPT.format(schema=schema_context, question=question)
    response = CHAT_MODEL.generate_content(prompt)
    return response.text.strip()


def run_query(sql: str) -> pd.DataFrame:
    conn = get_conn()
    return pd.read_sql(sql, conn)


# ── Streamlit UI ──────────────────────────────────────────────────────────────

def main():
    st.set_page_config(
        page_title="NomadHub — SQL Assistant",
        page_icon="🔍",
        layout="wide",
    )

    st.markdown("""
    <div style="background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
                padding: 2rem; border-radius: 12px; margin-bottom: 2rem;">
        <h1 style="color: white; margin: 0; font-size: 2rem;">🔍 NomadHub SQL Assistant</h1>
        <p style="color: rgba(255,255,255,0.9); margin: 0.5rem 0 0 0; font-size: 1.1rem;">
            Ask questions in plain English — powered by Google Gemini text-to-SQL
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Load schema
    schema_context = get_schema_context()

    st.markdown("**💡 Example questions:**")
    examples = [
        "What are the top 10 destinations by total revenue?",
        "Show monthly flight bookings by cabin class for 2024",
        "What is the cancellation rate by travel purpose?",
        "Which hotel categories have the highest average nightly rate?",
        "Show the top 5 airlines by number of completed bookings",
    ]
    cols = st.columns(len(examples))
    for col, ex in zip(cols, examples):
        if col.button(ex[:40] + "...", use_container_width=True, help=ex):
            st.session_state["nl_question"] = ex

    st.divider()

    question = st.text_area(
        "Your question:",
        value=st.session_state.get("nl_question", ""),
        placeholder="e.g. What is the average hotel booking value by country?",
        height=80,
    )

    col1, col2 = st.columns([1, 5])
    run_btn = col1.button("▶ Run Query", type="primary", use_container_width=True)
    col2.caption("Generates a SELECT query and runs it on your Snowflake MARTS schema")

    if run_btn and question:
        # Generate SQL
        with st.spinner("Generating SQL with Gemini..."):
            raw_sql = generate_sql(question, schema_context)

        st.markdown("### Generated SQL")
        is_safe, validated_sql = validate_sql(raw_sql)

        if not is_safe:
            st.error(f"🚫 SQL Validation Failed: {validated_sql}")
            st.code(raw_sql, language="sql")
            return

        st.code(validated_sql, language="sql")

        # Execute
        with st.spinner("Running query on Snowflake..."):
            try:
                df = run_query(validated_sql)
            except Exception as e:
                st.error(f"❌ Query execution failed: {e}")
                return

        # Results
        st.markdown(f"### Results ({len(df):,} rows)")
        if len(df) == 0:
            st.info("Query returned no results.")
        else:
            st.dataframe(df, use_container_width=True, height=400)

            # Quick visualisation hint
            if len(df.columns) >= 2:
                numeric_cols = df.select_dtypes("number").columns.tolist()
                cat_cols = df.select_dtypes(["object", "string"]).columns.tolist()
                if numeric_cols and cat_cols:
                    try:
                        import plotly.express as px
                        fig = px.bar(
                            df.head(20),
                            x=cat_cols[0],
                            y=numeric_cols[0],
                            title=f"{numeric_cols[0]} by {cat_cols[0]}",
                            template="plotly_white",
                            color_discrete_sequence=["#667eea"],
                        )
                        fig.update_layout(showlegend=False)
                        st.plotly_chart(fig, use_container_width=True)
                    except Exception:
                        pass

            # Download
            csv = df.to_csv(index=False)
            st.download_button(
                "⬇ Download CSV",
                csv,
                "nomad_hub_query_result.csv",
                "text/csv",
            )


if __name__ == "__main__":
    main()
