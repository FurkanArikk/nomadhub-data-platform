-- Stay bookings (synthetic, anchored on real reviews). Amounts are in the listing's
-- local currency (currency_code); USD conversion happens in fct_stay_bookings.

with source as (
    select * from {{ source('raw', 'stay_bookings') }}
)

select
    try_to_number(stay_booking_id)              as stay_booking_id,
    try_to_number(user_id)                      as user_id,
    try_to_number(listing_id)                   as listing_id,
    city,
    try_to_number(review_id)                    as review_id,
    try_to_timestamp_ntz(booked_at)             as booked_at,
    try_to_date(checkin_date)                   as checkin_date,
    try_to_date(checkout_date)                  as checkout_date,
    try_to_number(nights)                       as nights,
    try_to_number(guests)                       as guests,
    currency_code,
    try_to_number(nightly_rate, 14, 2)          as nightly_rate_local,
    try_to_number(cleaning_fee, 14, 2)          as cleaning_fee_local,
    try_to_number(service_fee, 14, 2)           as service_fee_local,
    try_to_number(total_amount, 14, 2)          as total_amount_local,
    payment_method,
    booking_channel,
    booking_status,
    try_to_timestamp_ntz(cancelled_at)          as cancelled_at,
    try_to_number(refund_amount, 14, 2)         as refund_amount_local,
    _loaded_at
from source
qualify row_number() over (partition by try_to_number(stay_booking_id) order by _loaded_at desc) = 1
