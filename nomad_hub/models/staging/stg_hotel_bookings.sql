-- Silver: stg_hotel_bookings
-- Clean hotel bookings. Derive RevPAR, occupancy contribution,
-- length of stay bucket, and cancellation flags.

with source as (
    select * from {{ source('raw', 'hotel_bookings') }}
),

cleaned as (
    select
        booking_id,
        upper(trim(booking_ref))                    as booking_ref,
        user_id,
        hotel_id,
        room_type,
        cast(check_in_date as date)                 as check_in_date,
        cast(check_out_date as date)                as check_out_date,
        cast(num_nights as int)                     as num_nights,
        cast(num_guests as int)                     as num_guests,
        cast(num_rooms as int)                      as num_rooms,
        round(cast(rate_per_night_usd as float), 2) as rate_per_night_usd,
        round(cast(total_rate_usd as float), 2)     as total_rate_usd,
        round(cast(taxes_usd as float), 2)          as taxes_usd,
        round(cast(total_amount_usd as float), 2)   as total_amount_usd,
        cast(booking_date as date)                  as booking_date,
        lower(booking_status)                       as booking_status,
        lower(payment_method)                       as payment_method,
        lower(travel_purpose)                       as travel_purpose,
        coalesce(is_refundable, false)              as is_refundable,
        coalesce(breakfast_included, false)         as breakfast_included,
        coalesce(airport_transfer, false)           as airport_transfer,
        nullif(trim(special_requests), '')          as special_requests,
        cast(created_at as date)                    as created_at,

        -- Derived: length of stay bucket
        case
            when cast(num_nights as int) = 1        then '1_night'
            when cast(num_nights as int) <= 3       then '2-3_nights'
            when cast(num_nights as int) <= 7       then '4-7_nights'
            when cast(num_nights as int) <= 14      then '8-14_nights'
            else '15+_nights'
        end                                         as los_bucket,

        -- Derived: advance booking days
        datediff(
            'day',
            cast(booking_date as date),
            cast(check_in_date as date)
        )                                           as advance_booking_days,

        -- Derived: revenue per available room night (simple proxy)
        round(
            cast(rate_per_night_usd as float) * cast(num_rooms as float),
            2
        )                                           as room_revenue_usd,

        -- Derived: is_cancelled flag
        (lower(booking_status) = 'cancelled')       as is_cancelled,

        -- Derived: recognised revenue (completed only)
        case
            when lower(booking_status) = 'completed'
            then round(cast(total_amount_usd as float), 2)
            else 0
        end                                         as recognised_revenue_usd,

        -- Derived: check-in month
        date_trunc('month', cast(check_in_date as date)) as check_in_month

    from source
    where booking_id is not null
      and user_id is not null
      and hotel_id is not null
      and cast(num_nights as int) > 0
      and cast(total_amount_usd as float) >= 0
)

select * from cleaned
