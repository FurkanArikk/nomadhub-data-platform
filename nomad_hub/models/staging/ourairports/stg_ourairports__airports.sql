-- OurAirports catalogue. Re-downloads overwrite the same file, which COPY INTO loads
-- again, so we keep the most recently loaded row per airport id.

with source as (
    select * from {{ source('raw', 'airports') }}
)

select
    try_to_number(id)                   as airport_id,
    ident                               as airport_ident,
    nullif(trim(iata_code), '')         as iata_code,
    nullif(trim(icao_code), '')         as icao_code,
    name                                as airport_name,
    type                                as airport_type,
    try_to_double(latitude_deg)         as latitude,
    try_to_double(longitude_deg)        as longitude,
    try_to_number(elevation_ft)         as elevation_ft,
    continent,
    iso_country                         as country_code,
    iso_region                          as region_code,
    municipality,
    scheduled_service = 'yes'           as has_scheduled_service,
    _loaded_at
from source
qualify row_number() over (partition by try_to_number(id) order by _loaded_at desc) = 1
