import plotly.graph_objects as go
import streamlit as st

from nomad.charts import palette, show, style
from nomad.data import query

st.title("City revenue")
st.caption("Completed stays only, in USD at the ECB rate on the booking date. "
           "Platform revenue = the service fee NomadHub keeps.")

year = st.segmented_control("Check-in year", list(range(2019, 2026)), default=2025) or 2025

cities = query("""
    select c.city_name as city,
           sum(r.gross_booking_value_usd)                    as gbv_usd,
           sum(r.platform_revenue_usd)                       as platform_revenue_usd,
           sum(r.nights_sold)                                as nights_sold,
           div0(sum(r.adr_usd * r.nights_sold), sum(r.nights_sold)) as adr_usd,
           div0(sum(r.cancelled_bookings), sum(r.bookings))  as cancellation_rate
    from MART_CITY_REVENUE r
    join DIM_CITIES c on c.city = r.city
    where year(r.month) = %s
    group by all
""", (year,))

left, right = st.columns(2)
with left:
    st.subheader(f"Gross booking value, {year}")
    d = cities.sort_values("gbv_usd")
    fig = go.Figure(go.Bar(x=d.gbv_usd, y=d.city, orientation="h", marker_color=palette()["single"],
                           hovertemplate="%{y}: $%{x:,.0f}<extra></extra>"))
    fig.update_xaxes(tickprefix="$")
    show(style(fig, height=560), d)

with right:
    st.subheader(f"Average daily rate (USD), {year}")
    d = cities.sort_values("adr_usd")
    fig = go.Figure(go.Bar(x=d.adr_usd, y=d.city, orientation="h", marker_color=palette()["single"],
                           hovertemplate="%{y}: $%{x:,.0f} per night<extra></extra>"))
    fig.update_xaxes(tickprefix="$")
    show(style(fig, height=560), d)
    st.caption("New York's short-term-rental law forces 30-night minimum stays: its stays average "
               "~17 nights, the longest of the 20 cities, priced closer to monthly rentals.")

st.subheader("Seasonality")
names = sorted(cities.city)
city = st.selectbox("City", names, index=names.index("Paris") if "Paris" in names else 0)
season = query("""
    select r.month, sum(r.nights_sold) as nights_sold
    from MART_CITY_REVENUE r join DIM_CITIES c on c.city = r.city
    where c.city_name = %s and r.month between '2019-01-01' and '2025-12-01'
    group by 1 order by 1
""", (city,))
fig = go.Figure(go.Scatter(x=season.month, y=season.nights_sold, mode="lines", name="Nights sold",
                           line_color=palette()["single"],
                           hovertemplate="%{y:,.0f} nights<extra></extra>"))
show(style(fig), season)
