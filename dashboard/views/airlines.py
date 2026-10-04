import plotly.graph_objects as go
import streamlit as st

from nomad.charts import AIRLINE_SLOTS, airline_color, palette, show, style
from nomad.data import query

st.title("Airline reliability")
st.caption("Every US domestic flight reported to the Bureau of Transportation Statistics, 2019–2025. "
           "On time = arrived < 15 min late, out of flights not cancelled or diverted (DOT definition).")

year = st.segmented_control("Year", list(range(2019, 2026)), default=2025)
year = year or 2025

ranking = query("""
    select airline_name, airline_code, carrier_type,
           sum(scheduled_flights)                                                            as flights,
           sum(on_time_flights) / sum(scheduled_flights - cancelled_flights - diverted_flights) as on_time_rate,
           sum(cancelled_flights) / sum(scheduled_flights)                                    as cancellation_rate
    from MART_AIRLINE_PERFORMANCE
    where year(month) = %s
    group by all
    order by on_time_rate
""", (year,))

left, right = st.columns(2)
with left:
    st.subheader(f"On-time arrival rate, {year}")
    # A dot plot, not bars: the interesting range is ~70-85%, and a bar whose axis doesn't
    # start at zero exaggerates the gaps. Dots are honest on a zoomed axis.
    fig = go.Figure(go.Scatter(
        x=ranking.on_time_rate, y=ranking.airline_name, mode="markers",
        marker={"size": 11, "color": palette()["single"]},
        customdata=ranking[["flights", "cancellation_rate"]],
        hovertemplate="%{y}: %{x:.1%} on time<br>%{customdata[0]:,.0f} flights · "
                      "%{customdata[1]:.1%} cancelled<extra></extra>",
    ))
    style(fig, height=520, percent_axis="x")
    fig.update_layout(hovermode="closest")
    fig.update_yaxes(showgrid=True)
    show(fig, ranking)

with right:
    st.subheader("Where the delay minutes come from")
    causes = query("""
        select year(month) as year,
               sum(carrier_delay_min) as carrier, sum(late_aircraft_delay_min) as late_aircraft,
               sum(nas_delay_min) as air_traffic_system, sum(weather_delay_min) as weather,
               sum(security_delay_min) as security
        from MART_AIRLINE_PERFORMANCE group by 1 order by 1
    """)
    labels = {"carrier": "Airline", "late_aircraft": "Late incoming aircraft",
              "air_traffic_system": "Air traffic system", "weather": "Weather", "security": "Security"}
    total = causes[list(labels)].sum(axis=1)
    fig = go.Figure()
    for i, (col, label) in enumerate(labels.items()):
        fig.add_bar(x=causes.year, y=causes[col] / total, name=label,
                    marker_color=palette()["series"][i],
                    hovertemplate=f"{label}: %{{y:.1%}}<extra></extra>")
    style(fig, height=520, percent_axis="y")
    fig.update_layout(barmode="stack", barcornerradius=0, legend_traceorder="normal")
    fig.update_xaxes(dtick=1)
    show(fig, causes)

st.subheader("Monthly on-time rate")
picked = st.multiselect(
    "Airlines (the 8 largest carriers, each with a fixed colour)",
    options=AIRLINE_SLOTS, default=["WN", "DL", "AA", "UA"], max_selections=4,
    format_func=lambda c: f"{c} · {ranking.set_index('airline_code').airline_name.get(c, c)}",
)
monthly = query("""
    select month, airline_code, airline_name,
           sum(on_time_flights) / sum(scheduled_flights - cancelled_flights - diverted_flights) as on_time_rate
    from MART_AIRLINE_PERFORMANCE group by all order by month
""")
fig = go.Figure()
for code in picked:
    d = monthly[monthly.airline_code == code]
    fig.add_scatter(x=d.month, y=d.on_time_rate, mode="lines", name=d.airline_name.iloc[0],
                    line_color=airline_color(code),
                    hovertemplate=f"{d.airline_name.iloc[0]}: %{{y:.1%}}<extra></extra>")
show(style(fig, height=380, percent_axis="y"), monthly[monthly.airline_code.isin(picked)])
