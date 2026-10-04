"""
NomadHub dashboard
==================
    streamlit run dashboard/app.py            (or: docker compose --profile app up -d)

Pages read the dbt marts as STREAMLIT_SVC / ANALYST_ROLE (read-only). The two AI pages
call Gemini: RAG over the review embeddings in Snowflake, and text-to-SQL.
"""

import sys
from pathlib import Path

import streamlit as st

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))                    # `nomad` helpers, importable from every page
sys.path.insert(0, str(HERE.parent / "ai"))      # rag / text_to_sql / common from the AI layer

st.set_page_config(page_title="NomadHub", page_icon="✈️", layout="wide")

pages = {
    "Analytics": [
        st.Page("views/overview.py", title="Overview", icon=":material/dashboard:", default=True),
        st.Page("views/airlines.py", title="Airline reliability", icon=":material/flight:"),
        st.Page("views/cities.py", title="City revenue", icon=":material/location_city:"),
        st.Page("views/occupancy.py", title="Forward occupancy", icon=":material/calendar_month:"),
        st.Page("views/reviews.py", title="Review insights", icon=":material/reviews:"),
    ],
    "AI": [
        st.Page("views/chat.py", title="Chat with reviews", icon=":material/forum:"),
        st.Page("views/ask.py", title="Ask the warehouse", icon=":material/database_search:"),
    ],
}

with st.sidebar:
    st.caption(
        "Real data: BTS flights, Inside Airbnb listings/calendar/reviews, OurAirports, ECB FX. "
        "Synthetic: users and bookings, generated on top of the real events."
    )

st.navigation(pages).run()
