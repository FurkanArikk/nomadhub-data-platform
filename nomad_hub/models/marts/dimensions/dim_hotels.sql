-- Gold: dim_hotels
-- Hotel dimension with enriched attributes and categorisation.

with hotels as (
    select * from {{ ref('stg_hotels') }}
),

countries as (
    select * from {{ ref('stg_countries') }}
),

joined as (
    select
        -- Surrogate key
        {{ dbt_utils.generate_surrogate_key(['h.hotel_id']) }} as hotel_sk,

        -- Natural key
        h.hotel_id,

        -- Hotel attributes
        h.hotel_name,
        h.category,
        h.star_rating,
        h.price_tier,
        h.amenity_score,

        -- Location
        h.country_code,
        coalesce(c.country_name, h.country_name)    as country_name,
        coalesce(c.region, 'Unknown')               as region,
        h.city,
        h.address,
        h.latitude,
        h.longitude,

        -- Inventory
        h.total_rooms,
        h.base_price_usd,

        -- Amenities (booleans)
        h.has_pool,
        h.has_spa,
        h.has_gym,
        h.has_restaurant,
        h.has_free_wifi,
        h.pet_friendly,

        -- Status
        h.is_active,
        h.opened_date,

        -- Derived: hotel age in years
        datediff('year', h.opened_date, current_date()) as hotel_age_years,

        -- Derived: is_resort (pool + >= 4 stars)
        (h.has_pool = true and h.star_rating >= 4)  as is_resort,

        -- Metadata
        h.created_at

    from hotels h
    left join countries c
        on h.country_code = c.country_code

    where h.hotel_id is not null
)

select * from joined
