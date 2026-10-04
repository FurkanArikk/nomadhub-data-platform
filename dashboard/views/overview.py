import plotly.graph_objects as go
import streamlit as st

from nomad.charts import palette, show, style
from nomad.data import query

st.title("NomadHub")
st.caption("A travel platform's data warehouse: 45.8M real US flights, 20 cities of real Airbnb "
           "supply and reviews, and 17.9M bookings generated on top of them.")

kpi = query("""
    select
        (select sum(scheduled_flights) from MART_AIRLINE_PERFORMANCE)                              as flights,
        (select sum(on_time_flights) / sum(scheduled_flights - cancelled_flights - diverted_flights)
           from MART_AIRLINE_PERFORMANCE where year(month) = 2025)                                as on_time_2025,
        (select sum(completed_stays) from MART_CITY_REVENUE)                                       as stays,
        (select sum(gross_booking_value_usd) from MART_CITY_REVENUE)                               as gbv_usd,
        (select sum(platform_revenue_usd) from MART_CITY_REVENUE)                                  as revenue_usd,
        (select count(*) from NOMAD_HUB.AI.REVIEW_ENRICHMENTS)                                     as enriched
""").iloc[0]

c = st.columns(5)
c[0].metric("US flights 2019–2025", f"{kpi.flights / 1e6:.1f}M")
c[1].metric("On-time rate, 2025", f"{kpi.on_time_2025:.1%}")
c[2].metric("Completed stays", f"{kpi.stays / 1e6:.1f}M")
c[3].metric("Gross booking value", f"${kpi.gbv_usd / 1e9:.1f}B")
c[4].metric("Platform revenue", f"${kpi.revenue_usd / 1e9:.2f}B")

left, right = st.columns(2)

with left:
    st.subheader("US flights per month")
    flights = query("""
        select month, sum(scheduled_flights) as flights
        from MART_AIRLINE_PERFORMANCE group by month order by month
    """)
    low = flights.loc[flights.flights.idxmin()]
    fig = go.Figure(go.Scatter(x=flights.month, y=flights.flights, mode="lines",
                               line_color=palette()["single"], name="Flights",
                               hovertemplate="%{y:,.0f} flights<extra></extra>"))
    fig.add_annotation(x=low.month, y=low.flights, text=f"{low.month:%b %Y}: {low.flights / 1e3:.0f}K flights",
                       showarrow=True, arrowhead=0, ax=70, ay=0, xanchor="left",
                       font={"color": palette()["muted"]}, arrowcolor=palette()["muted"])
    show(style(fig), flights)

with right:
    st.subheader("Completed stays per month")
    stays = query("""
        select month, sum(completed_stays) as completed_stays
        from MART_CITY_REVENUE where month between '2019-01-01' and '2025-11-01'
        group by month order by month
    """)
    fig = go.Figure(go.Scatter(x=stays.month, y=stays.completed_stays, mode="lines",
                               line_color=palette()["single"], name="Stays",
                               hovertemplate="%{y:,.0f} stays<extra></extra>"))
    show(style(fig), stays)
    st.caption("Stays are derived from reviews, which arrive after check-out, so the newest month is "
               "left out until its reviews are in.")

st.info(
    f"**What's real and what's generated.** Flights and their delays (BTS), listings, calendars and "
    f"review text (Inside Airbnb), airports (OurAirports) and exchange rates (ECB) are real. Users are "
    f"pseudonymised real reviewers; their bookings are generated from real reviews and placed on real "
    f"BTS flights. {int(kpi.enriched):,} reviews have been read by Gemini so far (grows daily via Airflow).",
    icon=":material/info:",
)
