-- Current state of each listing (latest snapshot). Price history is kept by the
-- snap_listings snapshot. Prices are in the city's LOCAL currency even though Inside
-- Airbnb prints them with a "$" — the currency comes from the cities seed.

with source as (
    select * from {{ source('raw', 'listings') }}
),

cities as (
    select * from {{ ref('cities') }}
)

select
    try_to_number(s.listing_id)                                         as listing_id,
    s.city,
    try_to_date(s.snapshot_date)                                        as snapshot_date,
    try_to_date(s.last_scraped)                                         as last_scraped_date,
    s.name                                                              as listing_name,
    {{ clean_html_text('s.description') }}                              as description,

    try_to_number(s.host_id)                                            as host_id,
    try_to_date(s.host_since)                                           as host_since,
    try_to_number(replace(s.host_response_rate, '%', '')) / 100         as host_response_rate,
    try_to_number(replace(s.host_acceptance_rate, '%', '')) / 100       as host_acceptance_rate,
    try_to_boolean(s.host_is_superhost)                                 as is_superhost,
    try_to_number(s.calculated_host_listings_count)                     as host_listings_count,

    s.neighbourhood_cleansed                                            as neighbourhood,
    s.neighbourhood_group_cleansed                                      as neighbourhood_group,
    try_to_double(s.latitude)                                           as latitude,
    try_to_double(s.longitude)                                          as longitude,

    s.property_type,
    s.room_type,
    try_to_number(s.accommodates)                                       as accommodates,
    try_to_number(s.bathrooms, 4, 1)                                    as bathrooms,
    s.bathrooms_text,
    try_to_number(s.bedrooms)                                           as bedrooms,
    try_to_number(s.beds)                                               as beds,
    try_parse_json(s.amenities)                                         as amenities,
    array_size(try_parse_json(s.amenities))                             as amenity_count,

    c.currency_code,
    try_to_number(replace(replace(s.price, '$', ''), ',', ''), 12, 2)   as price_local,
    try_to_number(s.minimum_nights)                                     as minimum_nights,
    try_to_number(s.maximum_nights)                                     as maximum_nights,
    try_to_boolean(s.has_availability)                                  as has_availability,
    try_to_number(s.availability_30)                                    as availability_30,
    try_to_number(s.availability_90)                                    as availability_90,
    try_to_number(s.availability_365)                                   as availability_365,
    try_to_boolean(s.instant_bookable)                                  as is_instant_bookable,
    nullif(trim(s.license), '')                                         as license,

    try_to_number(s.number_of_reviews)                                  as number_of_reviews,
    try_to_number(s.number_of_reviews_ltm)                              as number_of_reviews_ltm,
    try_to_date(s.first_review)                                         as first_review_date,
    try_to_date(s.last_review)                                          as last_review_date,
    try_to_number(s.review_scores_rating, 4, 2)                         as review_score_rating,
    try_to_number(s.review_scores_accuracy, 4, 2)                       as review_score_accuracy,
    try_to_number(s.review_scores_cleanliness, 4, 2)                    as review_score_cleanliness,
    try_to_number(s.review_scores_checkin, 4, 2)                        as review_score_checkin,
    try_to_number(s.review_scores_communication, 4, 2)                  as review_score_communication,
    try_to_number(s.review_scores_location, 4, 2)                       as review_score_location,
    try_to_number(s.review_scores_value, 4, 2)                          as review_score_value,

    try_to_number(s.estimated_occupancy_l365d)                          as estimated_occupied_nights_l365d,
    try_to_number(s.estimated_revenue_l365d, 14, 2)                     as estimated_revenue_local_l365d,

    s._source_file,
    s._loaded_at
from source s
left join cities c on c.city = s.city
qualify row_number() over (
    partition by try_to_number(s.listing_id)
    order by try_to_date(s.snapshot_date) desc, s._loaded_at desc
) = 1
