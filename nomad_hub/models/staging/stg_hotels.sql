-- Silver: stg_hotels
-- Standardise hotel data, derive price tier from category.

with source as (
    select * from {{ source('raw', 'hotels') }}
),

cleaned as (
    select
        hotel_id,
        trim(hotel_name)                    as hotel_name,
        category,
        cast(star_rating as int)            as star_rating,
        upper(country_code)                 as country_code,
        trim(country_name)                  as country_name,
        trim(city)                          as city,
        trim(address)                       as address,
        cast(latitude as float)             as latitude,
        cast(longitude as float)            as longitude,
        cast(total_rooms as int)            as total_rooms,
        round(cast(base_price_usd as float), 2) as base_price_usd,
        coalesce(has_pool, false)           as has_pool,
        coalesce(has_spa, false)            as has_spa,
        coalesce(has_gym, false)            as has_gym,
        coalesce(has_restaurant, false)     as has_restaurant,
        coalesce(has_free_wifi, true)       as has_free_wifi,
        coalesce(pet_friendly, false)       as pet_friendly,
        coalesce(is_active, true)           as is_active,
        cast(opened_date as date)           as opened_date,
        cast(created_at as date)            as created_at,

        -- Derived fields
        case
            when base_price_usd < 60    then 'budget'
            when base_price_usd < 150   then 'economy'
            when base_price_usd < 300   then 'midscale'
            when base_price_usd < 600   then 'upscale'
            when base_price_usd < 1500  then 'luxury'
            else 'ultra_luxury'
        end                                 as price_tier,

        -- Amenity score (0–5)
        (case when has_pool       then 1 else 0 end
         + case when has_spa      then 1 else 0 end
         + case when has_gym      then 1 else 0 end
         + case when has_restaurant then 1 else 0 end
         + case when pet_friendly then 1 else 0 end) as amenity_score

    from source
    where hotel_id is not null
      and hotel_name is not null
)

select * from cleaned
