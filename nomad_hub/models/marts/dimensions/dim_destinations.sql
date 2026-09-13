-- Gold: dim_destinations
-- Airport + country join to create a travel destination dimension.
-- Includes geographic hierarchy: airport → city → country → region.

with airports as (
    select * from {{ ref('stg_airports') }}
    where is_active = true
),

countries as (
    select * from {{ ref('stg_countries') }}
),

joined as (
    select
        -- Surrogate key
        {{ dbt_utils.generate_surrogate_key(['a.iata_code']) }} as destination_sk,

        -- Natural key
        a.iata_code,

        -- Airport attributes
        a.airport_id,
        a.airport_name,
        a.is_international,

        -- City / geo
        a.city,
        a.latitude,
        a.longitude,
        a.elevation_ft,

        -- Country attributes (from countries dim)
        a.country_code,
        coalesce(c.country_name, a.country_name)    as country_name,
        coalesce(c.region, 'Unknown')               as region,
        c.currency_code,
        c.language                                  as primary_language,
        c.visa_required,
        c.timezone,

        -- Metadata
        a.created_at

    from airports a
    left join countries c
        on a.country_code = c.country_code
)

select * from joined
