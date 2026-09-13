-- Silver: stg_reviews
-- Standardise review data. Normalise rating to 0–1 scale.
-- This view feeds both the MARTS layer and the AI enrichment pipeline.

with source as (
    select * from {{ source('raw', 'reviews') }}
),

cleaned as (
    select
        review_id,
        user_id,
        lower(trim(review_type))            as review_type,
        entity_id,
        trim(entity_name)                   as entity_name,
        trim(destination_city)              as destination_city,
        cast(rating as int)                 as rating,
        trim(review_title)                  as review_title,
        trim(review_text)                   as review_text,
        cast(coalesce(helpful_votes, 0) as int) as helpful_votes,
        coalesce(verified_booking, false)   as verified_booking,
        cast(review_date as date)           as review_date,
        lower(trim(language))               as language,
        cast(created_at as date)            as created_at,

        -- Derived: normalised rating (0.0–1.0)
        round((cast(rating as float) - 1.0) / 4.0, 4)  as rating_normalised,

        -- Derived: sentiment bucket from raw rating
        case
            when cast(rating as int) >= 4 then 'positive'
            when cast(rating as int) = 3  then 'neutral'
            else 'negative'
        end                                 as rating_sentiment,

        -- Derived: review length (proxy for review quality)
        length(trim(review_text))           as review_char_length,

        -- Derived: is_long_review (> 300 chars)
        (length(trim(review_text)) > 300)   as is_long_review,

        -- Derived: review year/month for time-series analysis
        year(cast(review_date as date))     as review_year,
        month(cast(review_date as date))    as review_month,
        date_trunc('month', cast(review_date as date)) as review_month_dt

    from source
    where review_id is not null
      and user_id is not null
      and review_text is not null
      and length(trim(review_text)) >= 10   -- filter empty/stub reviews
      and cast(rating as int) between 1 and 5
)

select * from cleaned
