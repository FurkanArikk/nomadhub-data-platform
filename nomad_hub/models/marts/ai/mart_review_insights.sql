-- What do guests talk about, and how do they feel about it?
-- One review can mention up to 3 topics, so a review counts once per topic.
-- Grain: review month × city × topic.

with enriched as (
    select
        r.review_id,
        r.city,
        date_trunc(month, r.review_date)::date  as month,
        e.language,
        e.sentiment,
        e.sentiment_score,
        e.complaint,
        e.mentions_travel_disruption,
        e.topics
    from {{ source('ai', 'review_enrichments') }} e
    join {{ ref('stg_airbnb__reviews') }} r on r.review_id = e.review_id
)

select
    month,
    city,
    t.value::varchar                                            as topic,
    count(*)                                                    as reviews,
    round(avg(sentiment_score), 3)                              as avg_sentiment_score,
    round(div0(count_if(sentiment = 'negative'), count(*)), 4)  as negative_share,
    round(div0(count_if(sentiment = 'mixed'), count(*)), 4)     as mixed_share,
    count_if(complaint is not null)                             as reviews_with_complaint,
    count_if(mentions_travel_disruption)                        as disruption_mentions,
    count(distinct language)                                    as languages
from enriched,
     lateral flatten(input => topics) t
group by all
