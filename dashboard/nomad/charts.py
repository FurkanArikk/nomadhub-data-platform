"""
Chart styling — one place for colour and mark rules.

Palette: the validated reference palette (fixed categorical order, single-hue
sequential, separate dark-mode steps). In light mode three slots sit below 3:1
contrast on the surface, so every chart ships with a table view (show()).
Rules: one y-axis per chart, thin 2px lines, 4px rounded bar ends, recessive grid,
legend only for 2+ series, colour follows the entity (never its rank).
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

LIGHT = {
    "series": ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"],
    "seq": ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"],
    "single": "#2a78d6",
    "grid": "#e8e7e3",
    "muted": "#6b6a66",
}
DARK = {
    "series": ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"],
    "seq": ["#0d366b", "#104281", "#184f95", "#256abf", "#3987e5", "#6da7ec", "#b7d3f6"],
    "single": "#3987e5",
    "grid": "#33332f",
    "muted": "#a3a29c",
}

# The 8 largest carriers by flights get fixed slots, so a carrier keeps its colour
# whatever else is selected.
AIRLINE_SLOTS = ["WN", "DL", "AA", "OO", "UA", "YX", "MQ", "B6"]


def palette() -> dict:
    theme = getattr(st.context, "theme", None)
    return DARK if theme is not None and theme.type == "dark" else LIGHT


def airline_color(code: str) -> str:
    return palette()["series"][AIRLINE_SLOTS.index(code)]


def style(fig: go.Figure, height: int = 380, percent_axis: str | None = None) -> go.Figure:
    p = palette()
    fig.update_layout(
        height=height,
        margin={"l": 8, "r": 8, "t": 36, "b": 8},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        hovermode="x unified" if any(t.type == "scatter" for t in fig.data) else "closest",
        barcornerradius=4,
        bargap=0.3,
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0, "title": None},
        showlegend=len(fig.data) > 1,
    )
    fig.update_xaxes(showgrid=False, linecolor=p["grid"], tickfont={"color": p["muted"]}, title=None)
    fig.update_yaxes(gridcolor=p["grid"], zeroline=False, tickfont={"color": p["muted"]}, title=None)
    fig.update_traces(line={"width": 2}, selector={"type": "scatter"})
    if percent_axis:
        getattr(fig, f"update_{percent_axis}axes")(tickformat=".0%")
    return fig


def show(fig: go.Figure, table: pd.DataFrame) -> None:
    """Render a chart plus its table view (the accessible, exact-value fallback)."""
    st.plotly_chart(fig, width="stretch", theme="streamlit", config={"displayModeBar": False})
    with st.expander("Table view"):
        st.dataframe(table, hide_index=True, width="stretch")
