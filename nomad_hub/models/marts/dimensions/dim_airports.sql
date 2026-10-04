-- Airports with an IATA code (the key BTS uses), with country/region names and the
-- NomadHub destination metro they serve, if any.

with catalogue as (
    select * from {{ ref('stg_ourairports__airports') }}
),

-- Historical codes BTS still reports but OurAirports no longer carries (renamed or
-- closed airports) are mapped onto the right airport via the airport_code_aliases seed.
with_aliases as (
    select * exclude (iata_code), iata_code from catalogue where iata_code is not null
    union all
    select c.* exclude (iata_code), al.iata_code
    from {{ ref('airport_code_aliases') }} al
    join catalogue c on c.airport_ident = al.airport_ident
),

airports as (
    select * from with_aliases
    -- a handful of IATA codes are reused by closed fields: prefer the one in service
    qualify row_number() over (
        partition by iata_code
        order by has_scheduled_service desc,
                 decode(airport_type, 'large_airport', 1, 'medium_airport', 2, 'small_airport', 3, 9),
                 airport_id
    ) = 1
)

select
    a.iata_code,
    a.icao_code,
    a.airport_name,
    a.airport_type,
    a.municipality,
    a.region_code,
    r.region_name,
    a.country_code,
    co.country_name,
    a.continent,
    a.latitude,
    a.longitude,
    a.elevation_ft,
    a.has_scheduled_service,
    ca.city         as nomad_city,
    ca.metro_key    as nomad_metro_key
from airports a
left join {{ ref('stg_ourairports__regions') }} r     on r.region_code = a.region_code
left join {{ ref('stg_ourairports__countries') }} co  on co.country_code = a.country_code
left join {{ ref('city_airports') }} ca               on ca.iata_code = a.iata_code
