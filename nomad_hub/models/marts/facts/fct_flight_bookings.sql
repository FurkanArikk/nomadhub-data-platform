{{ config(
    unique_key='flight_booking_id',
    cluster_by=['flight_date']
) }}

-- One row per booked flight leg. Each leg points at the REAL flight it was booked on
-- (fct_flights.flight_id), so its outcome — on time, delayed, cancelled — is real BTS data.

select
    flight_booking_id,
    stay_booking_id,
    user_id,
    flight_id,
    leg,
    booked_at,
    booked_at::date                                 as booking_date,
    flight_date,
    datediff(day, booked_at::date, flight_date)     as lead_time_days,
    airline_code,
    origin_airport,
    dest_airport,
    cabin_class,
    passengers,
    fare_per_passenger_usd,
    total_fare_usd,
    booking_status,
    _loaded_at
from {{ ref('stg_app__flight_bookings') }}
{% if is_incremental() %}
where _loaded_at > (select coalesce(max(_loaded_at), '1900-01-01'::timestamp_ltz) from {{ this }})
{% endif %}
