"""
NomadHub — Multi-Page Streamlit Dashboard
==========================================
Pages:
  📍 Overview         — KPIs, revenue trend, booking mix
  ✈️  Flight Analytics — Routes, cabin class, lead time
  🏨 Hotel Analytics  — Occupancy, RevPAR, category breakdown
  💬 Review Insights  — Sentiment, topics, AI enrichment
  🤖 Chat (RAG)       — Embedded rag_chat.py
  🔍 SQL Assistant    — Embedded text_to_sql.py

Run: streamlit run app.py
"""

import os
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import snowflake.connector
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title = "NomadHub Analytics",
    page_icon  = "✈️",
    layout     = "wide",
    initial_sidebar_state = "expanded",
)

# ── Shared style ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

* { font-family: 'Inter', sans-serif; }

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
}
[data-testid="stSidebar"] * { color: #e0e0e0 !important; }
[data-testid="stSidebar"] .stSelectbox label { color: #a0a0b0 !important; }

.metric-card {
    background: linear-gradient(135deg, #667eea22, #764ba222);
    border: 1px solid #667eea44;
    border-radius: 12px;
    padding: 1.2rem 1.5rem;
    text-align: center;
}
.metric-card h2 { color: #667eea; margin: 0; font-size: 2rem; font-weight: 700; }
.metric-card p  { color: #666; margin: 0.3rem 0 0 0; font-size: 0.9rem; }

.section-header {
    background: linear-gradient(90deg, #667eea, #764ba2);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-size: 1.4rem;
    font-weight: 600;
    margin: 1.5rem 0 0.5rem 0;
}
</style>
""", unsafe_allow_html=True)

# ── Snowflake connection ──────────────────────────────────────────────────────
@st.cache_resource
def get_conn():
    return snowflake.connector.connect(
        account   = os.environ["SNOWFLAKE_ACCOUNT"],
        user      = os.environ.get("SNOWFLAKE_USER", "ANALYST_USER"),
        password  = os.environ["SNOWFLAKE_PASSWORD"],
        database  = "NOMAD_HUB",
        warehouse = "NOMAD_WH",
        role      = "ANALYST_ROLE",
    )


@st.cache_data(ttl=1800, show_spinner=False)
def query(sql: str) -> pd.DataFrame:
    return pd.read_sql(sql, get_conn())


# ── Sidebar navigation ────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style='text-align:center; padding: 1rem 0 0.5rem 0;'>
        <div style='font-size: 2.5rem;'>✈️</div>
        <div style='font-size: 1.3rem; font-weight: 700; color: white;'>NomadHub</div>
        <div style='font-size: 0.75rem; color: #8888aa;'>Data Engineering Portfolio</div>
    </div>
    <hr style='border-color: #333355; margin: 0.5rem 0;'>
    """, unsafe_allow_html=True)

    page = st.selectbox(
        "Navigate to",
        [
            "📍 Overview",
            "✈️  Flight Analytics",
            "🏨 Hotel Analytics",
            "💬 Review Insights",
            "🤖 Chat with Reviews (RAG)",
            "🔍 SQL Assistant",
        ],
        label_visibility="collapsed",
    )

    st.markdown("<hr style='border-color: #333355;'>", unsafe_allow_html=True)
    st.markdown("""
    <div style='font-size: 0.7rem; color: #666688; text-align: center;'>
        <b>Tech Stack</b><br>
        Python · dbt · Snowflake<br>
        Airflow · Gemini · S3
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Overview
# ══════════════════════════════════════════════════════════════════════════════
if page == "📍 Overview":
    st.markdown("""
    <div style='background: linear-gradient(135deg, #667eea, #764ba2);
                padding: 1.5rem 2rem; border-radius: 12px; margin-bottom: 1.5rem;'>
        <h1 style='color: white; margin: 0;'>📍 NomadHub Overview</h1>
        <p style='color: rgba(255,255,255,0.8); margin: 0.3rem 0 0 0;'>
            Platform-wide KPIs and revenue performance
        </p>
    </div>
    """, unsafe_allow_html=True)

    # KPIs
    with st.spinner("Loading KPIs..."):
        kpis = query("""
        SELECT
            SUM(CASE WHEN revenue_type='flight' THEN total_bookings ELSE 0 END) AS flight_bookings,
            SUM(CASE WHEN revenue_type='hotel'  THEN total_bookings ELSE 0 END) AS hotel_bookings,
            SUM(recognised_revenue_usd)                                          AS total_revenue,
            AVG(cancellation_rate_pct)                                           AS avg_cancel_rate
        FROM NOMAD_HUB.MARTS.MART_REVENUE_SUMMARY
        WHERE date_id >= DATEADD('year', -1, CURRENT_DATE())
        """)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("✈️ Flight Bookings (1Y)",
                  f"{int(kpis['FLIGHT_BOOKINGS'].iloc[0]):,}")
    with c2:
        st.metric("🏨 Hotel Bookings (1Y)",
                  f"{int(kpis['HOTEL_BOOKINGS'].iloc[0]):,}")
    with c3:
        st.metric("💰 Revenue (1Y)",
                  f"${kpis['TOTAL_REVENUE'].iloc[0] / 1_000_000:.1f}M")
    with c4:
        st.metric("❌ Avg Cancellation Rate",
                  f"{kpis['AVG_CANCEL_RATE'].iloc[0]:.1f}%")

    # Revenue trend
    st.markdown('<p class="section-header">Monthly Revenue Trend</p>', unsafe_allow_html=True)
    with st.spinner("Loading revenue trend..."):
        rev = query("""
        SELECT
            month_start_date    AS month,
            revenue_type,
            SUM(recognised_revenue_usd) AS revenue
        FROM NOMAD_HUB.MARTS.MART_REVENUE_SUMMARY r
        JOIN NOMAD_HUB.MARTS.DIM_DATE d ON r.date_id = d.date_id
        WHERE r.date_id >= DATEADD('month', -18, CURRENT_DATE())
        GROUP BY 1, 2
        ORDER BY 1
        """)

    if not rev.empty:
        fig = px.area(
            rev, x="MONTH", y="REVENUE", color="REVENUE_TYPE",
            title="Monthly Recognised Revenue by Type",
            labels={"REVENUE": "Revenue (USD)", "MONTH": "Month", "REVENUE_TYPE": "Type"},
            color_discrete_map={"flight": "#667eea", "hotel": "#f093fb"},
            template="plotly_white",
        )
        fig.update_traces(line_width=2)
        fig.update_layout(hovermode="x unified", legend_title="")
        st.plotly_chart(fig, use_container_width=True)

    # Booking mix donut
    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<p class="section-header">Booking Mix</p>', unsafe_allow_html=True)
        mix = query("""
        SELECT revenue_type, SUM(total_bookings) AS bookings
        FROM NOMAD_HUB.MARTS.MART_REVENUE_SUMMARY
        WHERE date_id >= DATEADD('year', -1, CURRENT_DATE())
        GROUP BY 1
        """)
        if not mix.empty:
            fig = px.pie(
                mix, names="REVENUE_TYPE", values="BOOKINGS",
                hole=0.5, color_discrete_sequence=["#667eea", "#f093fb"],
                template="plotly_white",
            )
            fig.update_traces(textinfo="label+percent")
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown('<p class="section-header">Top Destinations by Revenue</p>', unsafe_allow_html=True)
        top_dest = query("""
        SELECT destination_city, destination_country, total_revenue_usd
        FROM NOMAD_HUB.MARTS.MART_DESTINATION_PERFORMANCE
        ORDER BY revenue_rank LIMIT 10
        """)
        if not top_dest.empty:
            fig = px.bar(
                top_dest, x="TOTAL_REVENUE_USD", y="DESTINATION_CITY",
                orientation="h", text_auto=".2s",
                color="TOTAL_REVENUE_USD",
                color_continuous_scale="Purples",
                template="plotly_white",
            )
            fig.update_layout(showlegend=False, coloraxis_showscale=False,
                              yaxis={"categoryorder": "total ascending"})
            st.plotly_chart(fig, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Flight Analytics
# ══════════════════════════════════════════════════════════════════════════════
elif page == "✈️  Flight Analytics":
    st.markdown("""
    <div style='background: linear-gradient(135deg, #4facfe, #00f2fe);
                padding: 1.5rem 2rem; border-radius: 12px; margin-bottom: 1.5rem;'>
        <h1 style='color: white; margin: 0;'>✈️ Flight Analytics</h1>
        <p style='color: rgba(255,255,255,0.85); margin: 0.3rem 0 0 0;'>
            Booking volumes, cabin class distribution, lead time patterns
        </p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown('<p class="section-header">Bookings by Cabin Class</p>', unsafe_allow_html=True)
        cabin = query("""
        SELECT cabin_class, COUNT(*) AS bookings, AVG(total_fare_usd) AS avg_fare
        FROM NOMAD_HUB.MARTS.FCT_FLIGHTS
        WHERE booking_date_id >= DATEADD('year', -1, CURRENT_DATE())
        GROUP BY 1 ORDER BY bookings DESC
        """)
        if not cabin.empty:
            fig = px.bar(
                cabin, x="CABIN_CLASS", y="BOOKINGS", color="AVG_FARE",
                text_auto=True, color_continuous_scale="Blues",
                template="plotly_white",
            )
            fig.update_layout(coloraxis_colorbar_title="Avg Fare")
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown('<p class="section-header">Lead Time Distribution</p>', unsafe_allow_html=True)
        lead = query("""
        SELECT lead_time_bucket, COUNT(*) AS bookings
        FROM NOMAD_HUB.MARTS.FCT_FLIGHTS
        WHERE booking_date_id >= DATEADD('year', -1, CURRENT_DATE())
        GROUP BY 1 ORDER BY bookings DESC
        """)
        if not lead.empty:
            fig = px.pie(
                lead, names="LEAD_TIME_BUCKET", values="BOOKINGS",
                hole=0.4, color_discrete_sequence=px.colors.sequential.Blues_r,
                template="plotly_white",
            )
            st.plotly_chart(fig, use_container_width=True)

    # Destination performance table
    st.markdown('<p class="section-header">Destination Performance Leaderboard</p>', unsafe_allow_html=True)
    dest_perf = query("""
    SELECT
        destination_city, destination_country, destination_region,
        total_inbound_flights, total_revenue_usd, avg_fare_usd,
        cancellation_rate_pct, most_popular_purpose
    FROM NOMAD_HUB.MARTS.MART_DESTINATION_PERFORMANCE
    ORDER BY revenue_rank
    LIMIT 20
    """)
    if not dest_perf.empty:
        dest_perf["TOTAL_REVENUE_USD"] = dest_perf["TOTAL_REVENUE_USD"].map("${:,.0f}".format)
        dest_perf["AVG_FARE_USD"] = dest_perf["AVG_FARE_USD"].map("${:,.0f}".format)
        st.dataframe(dest_perf, use_container_width=True, height=400)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Hotel Analytics
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🏨 Hotel Analytics":
    st.markdown("""
    <div style='background: linear-gradient(135deg, #f093fb, #f5576c);
                padding: 1.5rem 2rem; border-radius: 12px; margin-bottom: 1.5rem;'>
        <h1 style='color: white; margin: 0;'>🏨 Hotel Analytics</h1>
        <p style='color: rgba(255,255,255,0.85); margin: 0.3rem 0 0 0;'>
            Occupancy patterns, rate analysis, category performance
        </p>
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    hotel_kpis = query("""
    SELECT
        COUNT(DISTINCT booking_id)         AS total_bookings,
        AVG(rate_per_night_usd)            AS avg_nightly_rate,
        AVG(num_nights)                    AS avg_stay_length,
        SUM(recognised_revenue_usd)/1e6    AS revenue_m
    FROM NOMAD_HUB.MARTS.FCT_HOTEL_BOOKINGS
    WHERE check_in_date_id >= DATEADD('year', -1, CURRENT_DATE())
      AND booking_status = 'completed'
    """)
    c1.metric("📅 Completed Bookings (1Y)", f"{int(hotel_kpis['TOTAL_BOOKINGS'].iloc[0]):,}")
    c2.metric("💰 Avg Nightly Rate", f"${hotel_kpis['AVG_NIGHTLY_RATE'].iloc[0]:.0f}")
    c3.metric("🌙 Avg Stay Length", f"{hotel_kpis['AVG_STAY_LENGTH'].iloc[0]:.1f} nights")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<p class="section-header">Revenue by Hotel Category</p>', unsafe_allow_html=True)
        cat_rev = query("""
        SELECT h.category, SUM(b.recognised_revenue_usd) AS revenue, COUNT(*) AS bookings
        FROM NOMAD_HUB.MARTS.FCT_HOTEL_BOOKINGS b
        JOIN NOMAD_HUB.MARTS.DIM_HOTELS h ON b.hotel_sk = h.hotel_sk
        WHERE b.booking_status = 'completed'
        GROUP BY 1 ORDER BY revenue DESC
        """)
        if not cat_rev.empty:
            fig = px.bar(
                cat_rev, x="CATEGORY", y="REVENUE",
                color="BOOKINGS", text_auto=".2s",
                color_continuous_scale="RdPu",
                template="plotly_white",
            )
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown('<p class="section-header">Length of Stay Distribution</p>', unsafe_allow_html=True)
        los = query("""
        SELECT los_bucket, COUNT(*) AS bookings
        FROM NOMAD_HUB.MARTS.FCT_HOTEL_BOOKINGS
        WHERE booking_date_id >= DATEADD('year', -1, CURRENT_DATE())
        GROUP BY 1 ORDER BY bookings DESC
        """)
        if not los.empty:
            fig = px.bar(
                los, x="LOS_BUCKET", y="BOOKINGS",
                color_discrete_sequence=["#f093fb"],
                template="plotly_white",
            )
            st.plotly_chart(fig, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Review Insights (AI)
# ══════════════════════════════════════════════════════════════════════════════
elif page == "💬 Review Insights":
    st.markdown("""
    <div style='background: linear-gradient(135deg, #43e97b, #38f9d7);
                padding: 1.5rem 2rem; border-radius: 12px; margin-bottom: 1.5rem;'>
        <h1 style='color: white; margin: 0;'>💬 AI Review Intelligence</h1>
        <p style='color: rgba(255,255,255,0.85); margin: 0.3rem 0 0 0;'>
            Gemini-powered sentiment analysis and topic extraction
        </p>
    </div>
    """, unsafe_allow_html=True)

    with st.spinner("Loading enriched reviews..."):
        reviews = query("""
        SELECT
            review_type,
            rating,
            rating_sentiment,
            ai_sentiment,
            ai_sentiment_score,
            ai_category,
            ai_travel_type,
            ai_summary,
            review_year,
            review_month
        FROM NOMAD_HUB.AI.MART_REVIEW_INSIGHTS
        WHERE ai_sentiment IS NOT NULL
        LIMIT 50000
        """)

    if reviews.empty:
        st.info("⏳ No enriched reviews yet. Run `python ai/enrich_reviews.py` first.")
    else:
        col1, col2, col3 = st.columns(3)
        col1.metric("📝 Enriched Reviews", f"{len(reviews):,}")
        col2.metric("⭐ Avg Rating", f"{reviews['RATING'].mean():.2f}/5")
        col3.metric("😊 Positive %",
                    f"{(reviews['AI_SENTIMENT']=='positive').mean()*100:.1f}%")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown('<p class="section-header">Sentiment Distribution</p>', unsafe_allow_html=True)
            sent = reviews["AI_SENTIMENT"].value_counts().reset_index()
            fig = px.pie(
                sent, names="AI_SENTIMENT", values="count",
                color="AI_SENTIMENT",
                color_discrete_map={"positive":"#43e97b","neutral":"#f7d794","negative":"#f5576c"},
                hole=0.45, template="plotly_white",
            )
            st.plotly_chart(fig, use_container_width=True)

        with c2:
            st.markdown('<p class="section-header">Reviews by Category</p>', unsafe_allow_html=True)
            cats = reviews["AI_CATEGORY"].value_counts().head(10).reset_index()
            fig = px.bar(
                cats, x="count", y="AI_CATEGORY", orientation="h",
                color_discrete_sequence=["#38f9d7"],
                template="plotly_white",
            )
            fig.update_layout(yaxis={"categoryorder": "total ascending"})
            st.plotly_chart(fig, use_container_width=True)

        # Sample summaries
        st.markdown('<p class="section-header">AI-Generated Summaries (Sample)</p>', unsafe_allow_html=True)
        sample = reviews[reviews["AI_SUMMARY"].notna()].head(5)
        for _, row in sample.iterrows():
            sentiment_color = {"positive": "#43e97b", "neutral": "#f7d794", "negative": "#f5576c"}.get(
                row["AI_SENTIMENT"], "#ddd")
            st.markdown(f"""
            <div style="border-left: 4px solid {sentiment_color}; padding: 0.75rem 1rem;
                        background: {sentiment_color}15; border-radius: 6px; margin-bottom: 0.5rem;">
                <b>{row['REVIEW_TYPE'].title()}</b> | 
                ⭐ {row['RATING']}/5 | 
                🏷️ {row.get('AI_CATEGORY','—')} | 
                🧳 {row.get('AI_TRAVEL_TYPE','—')}<br>
                <span style="color: #444; font-size: 0.9rem;">{row['AI_SUMMARY']}</span>
            </div>
            """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Chat with Reviews (RAG) — embedded
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🤖 Chat with Reviews (RAG)":
    # Import and run the RAG chat module
    ai_dir = Path(__file__).parent.parent / "ai"
    sys.path.insert(0, str(ai_dir))
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("rag_chat", ai_dir / "rag_chat.py")
        rag_module = importlib.util.load_from_spec(spec)
        spec.loader.exec_module(rag_module)
        rag_module.main()
    except Exception as e:
        st.error(f"Could not load RAG chat: {e}")
        st.info("Run: `streamlit run ai/rag_chat.py` directly instead.")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: SQL Assistant — embedded
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🔍 SQL Assistant":
    ai_dir = Path(__file__).parent.parent / "ai"
    sys.path.insert(0, str(ai_dir))
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("text_to_sql", ai_dir / "text_to_sql.py")
        sql_module = importlib.util.load_from_spec(spec)
        spec.loader.exec_module(sql_module)
        sql_module.main()
    except Exception as e:
        st.error(f"Could not load SQL assistant: {e}")
        st.info("Run: `streamlit run ai/text_to_sql.py` directly instead.")
