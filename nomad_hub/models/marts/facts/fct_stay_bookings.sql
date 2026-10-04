{{ config(
    unique_key='stay_booking_id',
    cluster_by=['checkin_date']
) }}

-- One row per stay booking (completed or cancelled), amounts in local currency AND USD.
-- USD uses the ECB rate on the booking date — what the guest was charged that day.
-- Platform revenue = service fee on completed stays.

with bookings as (
    select * from {{ ref('stg_app__stay_bookings') }}
    {% if is_incremental() %}
    where _loaded_at > (select coalesce(max(_loaded_at), '1900-01-01'::timestamp_ltz) from {{ this }})
    {% endif %}
),

fx as (
    select * from {{ ref('fx_rates_daily') }}
)

select
    b.stay_booking_id,
    b.user_id,
    b.listing_id,
    b.city,
    b.review_id,
    b.review_id is not null                                       as has_review,
    b.booked_at,
    b.booked_at::date                                             as booking_date,
    b.checkin_date,
    b.checkout_date,
    datediff(day, b.booked_at::date, b.checkin_date)              as lead_time_days,
    b.nights,
    b.guests,
    b.booking_status,
    b.booking_status = 'cancelled'                                as is_cancelled,
    b.cancelled_at,
    b.payment_method,
    b.booking_channel,

    b.currency_code,
    b.nightly_rate_local,
    b.total_amount_local,
    fx.usd_per_unit                                               as fx_usd_per_unit,
    round(b.nightly_rate_local  * fx.usd_per_unit, 2)             as nightly_rate_usd,
    round(b.nightly_rate_local * b.nights * fx.usd_per_unit, 2)   as accommodation_usd,
    round(b.cleaning_fee_local  * fx.usd_per_unit, 2)             as cleaning_fee_usd,
    round(b.service_fee_local   * fx.usd_per_unit, 2)             as service_fee_usd,
    round(b.total_amount_local  * fx.usd_per_unit, 2)             as total_amount_usd,
    round(b.refund_amount_local * fx.usd_per_unit, 2)             as refund_amount_usd,
    b._loaded_at
from bookings b
left join fx
  on fx.currency_code = b.currency_code
 and fx.rate_date = b.booked_at::date
