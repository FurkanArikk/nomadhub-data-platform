import plotly.graph_objects as go
import streamlit as st

from nomad.charts import palette, show, style
from nomad.data import query

st.title("Forward occupancy")
st.caption("From the 188M-row Inside Airbnb calendar: for each listing, whether each of the next 365 "
           "nights is still bookable. An unavailable night is booked *or* blocked by the host, so this "
           "is an upper-bound proxy for occupancy, not a booking count.")

occ = query("""
    select c.city_name as city, o.month,
           div0(sum(o.unavailable_nights), sum(o.listing_nights)) as occupancy_proxy,
           sum(o.listing_nights)                                  as listing_nights
    from MART_FORWARD_OCCUPANCY o
    join DIM_CITIES c on c.city = o.city
    group by all
    order by city, month
""")
# 12 full forward months (the snapshot month and the 13th month are partial)
months = sorted(occ.month.unique())[1:13]
occ = occ[occ.month.isin(months)]

grid = occ.pivot(index="city", columns="month", values="occupancy_proxy")
grid = grid.loc[grid.mean(axis=1).sort_values().index]

seq = palette()["seq"]
fig = go.Figure(go.Heatmap(
    z=grid.values, x=[m.strftime("%b %Y") for m in grid.columns], y=grid.index,
    colorscale=[[i / (len(seq) - 1), c] for i, c in enumerate(seq)],
    xgap=2, ygap=2, colorbar={"tickformat": ".0%", "thickness": 10, "title": None},
    hovertemplate="%{y}, %{x}: %{z:.0%} of nights unavailable<extra></extra>",
))
st.subheader("Share of nights already unavailable, next 12 months")
show(style(fig, height=620), occ)
st.caption("Near-term months look fuller because they have had more time to be booked; "
           "compare cities within a column, not months within a row.")
