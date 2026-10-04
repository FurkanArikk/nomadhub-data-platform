-- The 20 destination cities with their airports and listing supply.

with listings as (
    select city, count(*) as listings, count_if(room_type = 'Entire home/apt') as entire_homes
    from {{ ref('stg_airbnb__listings') }}
    group by city
),

airports as (
    select city, array_agg(iata_code) within group (order by iata_code) as airport_codes
    from {{ ref('city_airports') }}
    group by city
)

select
    c.city,
    c.city_name,
    c.country_code,
    co.country_name,
    c.currency_code,
    c.is_us,
    a.airport_codes,
    coalesce(l.listings, 0)       as listings,
    coalesce(l.entire_homes, 0)   as entire_homes
from {{ ref('cities') }} c
left join {{ ref('stg_ourairports__countries') }} co on co.country_code = c.country_code
left join airports a on a.city = c.city
left join listings l on l.city = c.city
