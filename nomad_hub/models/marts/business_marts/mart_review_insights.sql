-- Gold → AI Schema: mart_review_insights
-- Reads from AI.REVIEW_ENRICHED (populated by ai/enrich_reviews.py)
-- and joins back to staging reviews + dimension context.
-- Powers the "Review Intelligence" page in Streamlit.

{{
    config(
        schema='AI',
        materialized='table'
    )
}}

with enriched_reviews as (
    -- This table is created by ai/enrich_reviews.py via Gemini API
    select *
    from {{ source('ai', 'review_enriched') }}
),

stg_reviews as (
    select * from {{ ref('stg_reviews') }}
),

joined as (
    select
        r.review_id,
        r.user_id,
        r.review_type,
        r.entity_id,
        r.entity_name,
        r.destination_city,
        r.rating,
        r.rating_normalised,
        r.rating_sentiment,
        r.review_title,
        r.review_text,
        r.review_char_length,
        r.is_long_review,
        r.helpful_votes,
        r.verified_booking,
        r.review_date,
        r.review_year,
        r.review_month,
        r.language,

        -- AI-enriched columns (from Gemini)
        e.ai_sentiment,
        e.ai_sentiment_score,
        e.ai_category,
        e.ai_travel_type,
        e.ai_summary,
        e.ai_key_topics,
        e.ai_service_score,
        e.ai_value_score,
        e.ai_location_score,
        e.ai_cleanliness_score,
        e.ai_staff_score,
        e.enriched_at

    from stg_reviews r
    left join enriched_reviews e
        on r.review_id = e.review_id
)

select * from joined
