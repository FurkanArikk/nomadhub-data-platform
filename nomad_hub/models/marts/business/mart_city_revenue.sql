-- How much does each city earn, and how, each month?
-- Grain: check-in month × city × room type. All money in USD (ECB rate at booking).
--   gross_booking_value  what guests paid for completed stays
--   platform_revenue     NomadHub's take = service fee on completed stays
--   ADR                  average daily rate = accommodation USD / nights sold

with stays as (
    select s.*, l.room_type
    from {{ ref('fct_stay_bookings') }} s
    left join {{ ref('dim_listings') }} l on l.listing_id = s.listing_id
)

select
    date_trunc(month, checkin_date)::date                               as month,
    city,
    room_type,

    count(*)                                                            as bookings,
    count_if(not is_cancelled)                                          as completed_stays,
    count_if(is_cancelled)                                              as cancelled_bookings,
    round(div0(count_if(is_cancelled), count(*)), 4)                    as cancellation_rate,
    count(distinct iff(not is_cancelled, user_id, null))                as unique_guests,

    sum(iff(not is_cancelled, nights, 0))                               as nights_sold,
    sum(iff(not is_cancelled, guests * nights, 0))                      as guest_nights,
    round(avg(iff(not is_cancelled, nights, null)), 2)                  as avg_length_of_stay,
    round(avg(lead_time_days), 1)                                       as avg_lead_time_days,

    round(sum(iff(not is_cancelled, total_amount_usd, 0)), 2)           as gross_booking_value_usd,
    round(sum(iff(not is_cancelled, service_fee_usd, 0)), 2)            as platform_revenue_usd,
    round(sum(iff(is_cancelled, refund_amount_usd, 0)), 2)              as refunds_usd,
    round(div0(sum(iff(not is_cancelled, accommodation_usd, 0)),
               sum(iff(not is_cancelled, nights, 0))), 2)               as adr_usd
from stays
group by all
