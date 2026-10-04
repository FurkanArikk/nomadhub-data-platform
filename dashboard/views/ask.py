import plotly.graph_objects as go
import streamlit as st

import text_to_sql  # ai/text_to_sql.py (ai/ is on sys.path, see app.py)
from nomad.charts import palette, show, style
from nomad.data import connection, numeric

st.title("Ask the warehouse")
st.caption("Gemini writes one Snowflake SELECT from the live schema of the MARTS and AI tables. A guard "
           "rejects anything else, and the query runs as ANALYST_ROLE, which can only read — the role is "
           "the real safety boundary.")

EXAMPLES = [
    "Which airline had the worst on-time rate in 2025?",
    "Top 5 cities by platform revenue in 2024",
    "Average daily rate in USD by city for entire homes in 2025",
    "How did monthly flight volume change during 2020?",
]


@st.cache_data(ttl=3600, show_spinner=False)
def schema() -> str:
    return text_to_sql.schema_description(connection())


cols = st.columns(len(EXAMPLES))
for col, example in zip(cols, EXAMPLES, strict=True):
    if col.button(example, width="stretch"):
        st.session_state.question = example

question = st.text_input("Your question", key="question",
                         placeholder="e.g. Which month of 2024 had the most cancellations?")

if question:
    with st.spinner("Writing SQL…"):
        result = text_to_sql.generate_sql(question, schema())
    st.markdown(f"*{result.explanation}*")
    st.code(result.sql, language="sql", wrap_lines=True)

    ok, sql_or_reason = text_to_sql.is_safe(result.sql)
    if not ok:
        st.error(f"Rejected by the guard: {sql_or_reason}")
        st.stop()
    try:
        df = text_to_sql.run(sql_or_reason, connection())
    except Exception as exc:          # show Snowflake's message rather than a stack trace
        st.error(f"Snowflake error: {exc}")
        st.stop()

    df.columns = [c.lower() for c in df.columns]
    df = numeric(df)
    st.caption(f"{len(df):,} rows" + (" (capped)" if len(df) == text_to_sql.MAX_ROWS else ""))
    numeric = df.select_dtypes("number").columns
    if len(df.columns) == 2 and len(numeric) == 1 and 1 < len(df) <= 40:
        label, value = [c for c in df.columns if c not in numeric][0], numeric[0]
        fig = go.Figure(go.Bar(x=df[value], y=df[label].astype(str), orientation="h",
                               marker_color=palette()["single"],
                               hovertemplate="%{y}: %{x:,.4~g}<extra></extra>"))
        fig.update_yaxes(autorange="reversed")      # keep the query's ORDER BY top-down
        show(style(fig, height=max(240, 28 * len(df))), df)
    else:
        st.dataframe(df, hide_index=True, width="stretch")
