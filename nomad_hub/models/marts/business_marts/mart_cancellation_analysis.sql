-- Gold: mart_cancellation_analysis
-- ✨ NEW: Deep cancellation analysis across flights and hotels.
-- Powers the "Cancellation Intelligence" section in Streamlit.
-- Identifies patterns: which cabin class / hotel category / purpose cancels most.

with flight_cancel as (
    select
        'flight'                            as booking_type,
        date_trunc('month', booking_date_id) as booking_month,
        cabin_class                         as segment,
        travel_purpose,
        lead_time_bucket,
        is_refundable,

        count(*)                            as total_bookings,
        sum(case when is_cancelled then 1 else 0 end)       as cancelled_count,
        sum(case when is_cancelled then total_fare_usd else 0 end) as cancelled_revenue_usd,
        round(
            sum(case when is_cancelled then 1 else 0 end) * 100.0
            / nullif(count(*), 0), 2
        )                                   as cancellation_rate_pct,
        avg(advance_booking_days)           as avg_advance_days

    from {{ ref('fct_flights') }}
    group by 1, 2, 3, 4, 5, 6
),

hotel_cancel as (
    select
        'hotel'                             as booking_type,
        date_trunc('month', booking_date_id) as booking_month,
        h.category                          as segment,
        b.travel_purpose,
        b.los_bucket                        as lead_time_bucket,
        b.is_refundable,

        count(*)                            as total_bookings,
        sum(case when b.is_cancelled then 1 else 0 end)         as cancelled_count,
        sum(case when b.is_cancelled then b.total_amount_usd else 0 end) as cancelled_revenue_usd,
        round(
            sum(case when b.is_cancelled then 1 else 0 end) * 100.0
            / nullif(count(*), 0), 2
        )                                   as cancellation_rate_pct,
        avg(b.advance_booking_days)         as avg_advance_days

    from {{ ref('fct_hotel_bookings') }} b
    inner join {{ ref('dim_hotels') }} h
        on b.hotel_sk = h.hotel_sk
    group by 1, 2, 3, 4, 5, 6
),

combined as (
    select * from flight_cancel
    union all
    select * from hotel_cancel
)

select
    c.*,
    d.year,
    d.quarter_label,
    d.month_name,
    d.month_num

from combined c
left join {{ ref('dim_date') }} d
    on c.booking_month = d.date_id

order by booking_month, booking_type, cancellation_rate_pct desc
