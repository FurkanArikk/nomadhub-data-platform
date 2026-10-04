-- Current listing attributes. price_usd uses the ECB rate on the snapshot date.
-- Historical prices: see snapshot snap_listings.

with listings as (
    select * from {{ ref('stg_airbnb__listings') }}
),

fx as (
    select * from {{ ref('fx_rates_daily') }}
)

select
    l.listing_id,
    l.city,
    l.listing_name,
    l.neighbourhood,
    l.neighbourhood_group,
    l.latitude,
    l.longitude,
    l.property_type,
    l.room_type,
    l.accommodates,
    l.bedrooms,
    l.beds,
    l.bathrooms,
    l.amenity_count,
    l.host_id,
    l.is_superhost,
    l.host_listings_count,
    l.host_listings_count > 1                         as is_multi_listing_host,
    l.minimum_nights,
    l.minimum_nights >= 30                            as is_long_term_only,
    l.currency_code,
    l.price_local,
    round(l.price_local * fx.usd_per_unit, 2)         as price_usd,
    case
        when l.price_local is null then null
        when l.price_local * fx.usd_per_unit < 75  then 'budget'
        when l.price_local * fx.usd_per_unit < 150 then 'mid'
        when l.price_local * fx.usd_per_unit < 300 then 'upscale'
        else 'luxury'
    end                                               as price_band,
    l.availability_365,
    l.number_of_reviews,
    l.number_of_reviews_ltm,
    l.first_review_date,
    l.last_review_date,
    l.review_score_rating,
    l.review_score_cleanliness,
    l.review_score_location,
    l.review_score_value,
    l.estimated_occupied_nights_l365d,
    round(l.estimated_revenue_local_l365d * fx.usd_per_unit, 2) as estimated_revenue_usd_l365d,
    l.snapshot_date
from listings l
left join fx
  on fx.currency_code = l.currency_code
 and fx.rate_date = l.snapshot_date
