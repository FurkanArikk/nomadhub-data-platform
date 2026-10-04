-- Flight bookings (synthetic) on real BTS flights. flight_id is built with the same
-- flight_key macro as stg_bts__flights, so every booking joins to its real flight.

with source as (
    select * from {{ source('raw', 'flight_bookings') }}
)

select
    try_to_number(flight_booking_id)            as flight_booking_id,
    try_to_number(stay_booking_id)              as stay_booking_id,
    try_to_number(user_id)                      as user_id,
    {{ flight_key('flight_date', 'airline_code', 'flight_number', 'origin', 'dest', 'crs_dep_time') }}
                                                as flight_id,
    leg,
    try_to_timestamp_ntz(booked_at)             as booked_at,
    try_to_date(flight_date)                    as flight_date,
    upper(airline_code)                         as airline_code,
    upper(origin)                               as origin_airport,
    upper(dest)                                 as dest_airport,
    cabin_class,
    try_to_number(passengers)                   as passengers,
    try_to_number(fare_per_passenger_usd, 12, 2) as fare_per_passenger_usd,
    try_to_number(total_fare_usd, 12, 2)        as total_fare_usd,
    booking_status,
    _loaded_at
from source
qualify row_number() over (partition by try_to_number(flight_booking_id) order by _loaded_at desc) = 1
