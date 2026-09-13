-- Silver: stg_flights
-- Clean flight bookings. Derive advance booking days, trip duration,
-- is_cancelled flag, and lead_time bucket.

with source as (
    select * from {{ source('raw', 'flights') }}
),

cleaned as (
    select
        flight_id,
        upper(trim(booking_ref))                    as booking_ref,
        user_id,
        upper(trim(origin_iata))                    as origin_iata,
        upper(trim(destination_iata))               as destination_iata,
        trim(airline)                               as airline,
        upper(trim(flight_number))                  as flight_number,
        cabin_class,
        cast(outbound_date as date)                 as outbound_date,
        cast(nullif(return_date, '') as date)       as return_date,
        coalesce(is_round_trip, false)              as is_round_trip,
        cast(num_passengers as int)                 as num_passengers,
        round(cast(base_fare_usd as float), 2)      as base_fare_usd,
        round(cast(taxes_usd as float), 2)          as taxes_usd,
        round(cast(total_fare_usd as float), 2)     as total_fare_usd,
        cast(booking_date as date)                  as booking_date,
        lower(booking_status)                       as booking_status,
        lower(payment_method)                       as payment_method,
        lower(travel_purpose)                       as travel_purpose,
        coalesce(is_refundable, false)              as is_refundable,
        cast(coalesce(checked_bags, 0) as int)      as checked_bags,
        cast(created_at as date)                    as created_at,

        -- Derived: days booked in advance
        datediff(
            'day',
            cast(booking_date as date),
            cast(outbound_date as date)
        )                                           as advance_booking_days,

        -- Derived: lead-time bucket
        case
            when datediff('day', cast(booking_date as date), cast(outbound_date as date)) = 0 then 'same_day'
            when datediff('day', cast(booking_date as date), cast(outbound_date as date)) <= 7  then '1-7_days'
            when datediff('day', cast(booking_date as date), cast(outbound_date as date)) <= 30 then '8-30_days'
            when datediff('day', cast(booking_date as date), cast(outbound_date as date)) <= 90 then '31-90_days'
            else '90+_days'
        end                                         as lead_time_bucket,

        -- Derived: fare per passenger
        round(
            cast(total_fare_usd as float) / nullif(cast(num_passengers as int), 0),
            2
        )                                           as fare_per_passenger_usd,

        -- Derived: is_cancelled flag
        (lower(booking_status) = 'cancelled')       as is_cancelled,

        -- Derived: revenue (only completed bookings)
        case
            when lower(booking_status) = 'completed'
            then round(cast(total_fare_usd as float), 2)
            else 0
        end                                         as recognised_revenue_usd,

        -- Derived: booking month
        date_trunc('month', cast(booking_date as date)) as booking_month

    from source
    where flight_id is not null
      and user_id is not null
      and origin_iata != destination_iata  -- remove data-gen artifacts
)

select * from cleaned
