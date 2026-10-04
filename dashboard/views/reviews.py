import plotly.graph_objects as go
import streamlit as st

from nomad.charts import palette, show, style
from nomad.data import query

st.title("Review insights")
st.caption("Real guest reviews, read by Gemini: sentiment, language, topics and the main complaint. "
           "A sample is enriched each day by the Airflow DAG.")

stats = query("""
    select count(*) as reviews, count(distinct language) as languages,
           avg(iff(sentiment = 'negative', 1, 0)) as negative_share,
           avg(sentiment_score) as avg_score
    from NOMAD_HUB.AI.REVIEW_ENRICHMENTS
""").iloc[0]
c = st.columns(4)
c[0].metric("Reviews enriched", f"{int(stats.reviews):,}")
c[1].metric("Languages", int(stats.languages))
c[2].metric("Negative", f"{stats.negative_share:.1%}")
c[3].metric("Average sentiment", f"{stats.avg_score:+.2f}", help="-1 very negative … +1 very positive")

left, right = st.columns(2)
with left:
    st.subheader("Share of negative or mixed reviews, by topic")
    topics = query("""
        select t.value::varchar as topic, count(*) as reviews,
               avg(iff(e.sentiment in ('negative', 'mixed'), 1, 0)) as critical_share
        from NOMAD_HUB.AI.REVIEW_ENRICHMENTS e, lateral flatten(input => e.topics) t
        group by 1 having count(*) >= 10 order by critical_share
    """)
    fig = go.Figure(go.Bar(x=topics.critical_share, y=topics.topic, orientation="h",
                           marker_color=palette()["single"], customdata=topics[["reviews"]],
                           hovertemplate="%{y}: %{x:.1%} critical (%{customdata[0]} reviews)<extra></extra>"))
    show(style(fig, height=440, percent_axis="x"), topics)

with right:
    st.subheader("Review languages")
    langs = query("""
        select language, count(*) as reviews from NOMAD_HUB.AI.REVIEW_ENRICHMENTS
        group by 1 order by 2 desc limit 10
    """).sort_values("reviews")
    fig = go.Figure(go.Bar(x=langs.reviews, y=langs.language, orientation="h",
                           marker_color=palette()["single"],
                           hovertemplate="%{y}: %{x} reviews<extra></extra>"))
    show(style(fig, height=440), langs)

st.subheader("What critical guests say")
complaints = query("""
    select r.city, r.review_date, e.sentiment, e.complaint, e.summary_en
    from NOMAD_HUB.AI.REVIEW_ENRICHMENTS e
    join NOMAD_HUB.STAGING.STG_AIRBNB__REVIEWS r on r.review_id = e.review_id
    where e.sentiment in ('negative', 'mixed') and e.complaint is not null
    order by r.review_date desc limit 50
""")
st.dataframe(complaints, hide_index=True, width="stretch")

with st.expander("Delay impact — read this before drawing conclusions"):
    st.markdown(
        "`mart_delay_impact` joins each stay's review to the **real** arrival delay of the BTS flight the "
        "guest was booked on. The reviews are real, but which flight a guest took is **generated**, so the "
        "review cannot know about that delay — expect no effect. It demonstrates the three-way join "
        "(Inside Airbnb × BTS × LLM), not a finding."
    )
    st.dataframe(query("select * from NOMAD_HUB.AI.MART_DELAY_IMPACT order by delay_bucket"),
                 hide_index=True, width="stretch")
