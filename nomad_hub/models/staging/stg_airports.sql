-- Silver: stg_airports
-- Clean and standardise airport data. Filter inactive airports.

with source as (
    select * from {{ source('raw', 'airports') }}
),

cleaned as (
    select
        airport_id,
        upper(trim(iata_code))                  as iata_code,
        trim(airport_name)                      as airport_name,
        trim(city)                              as city,
        upper(country_code)                     as country_code,
        trim(country_name)                      as country_name,
        cast(latitude as float)                 as latitude,
        cast(longitude as float)                as longitude,
        coalesce(cast(elevation_ft as int), 0)  as elevation_ft,
        coalesce(is_international, false)       as is_international,
        coalesce(is_active, true)               as is_active,
        cast(created_at as date)                as created_at
    from source
    where airport_id is not null
      and iata_code is not null
      and length(trim(iata_code)) = 3
)

select * from cleaned
