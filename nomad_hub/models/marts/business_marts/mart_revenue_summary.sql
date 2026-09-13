-- Gold: mart_revenue_summary
-- Daily revenue roll-up combining flight and hotel bookings.
-- Powers the main Overview dashboard KPIs.

with flight_daily as (
    select
        booking_date_id                             as date_id,
        'flight'                                    as revenue_type,
        count(*)                                    as total_bookings,
        sum(case when is_cancelled then 1 else 0 end) as cancelled_bookings,
        sum(recognised_revenue_usd)                 as recognised_revenue_usd,
        sum(total_fare_usd)                         as gross_revenue_usd,
        avg(total_fare_usd)                         as avg_booking_value_usd,
        sum(num_passengers)                         as total_pax
    from {{ ref('fct_flights') }}
    group by 1
),

hotel_daily as (
    select
        booking_date_id                             as date_id,
        'hotel'                                     as revenue_type,
        count(*)                                    as total_bookings,
        sum(case when is_cancelled then 1 else 0 end) as cancelled_bookings,
        sum(recognised_revenue_usd)                 as recognised_revenue_usd,
        sum(total_amount_usd)                       as gross_revenue_usd,
        avg(total_amount_usd)                       as avg_booking_value_usd,
        sum(num_guests)                             as total_pax
    from {{ ref('fct_hotel_bookings') }}
    group by 1
),

combined as (
    select * from flight_daily
    union all
    select * from hotel_daily
),

with_date as (
    select
        c.*,
        d.year,
        d.quarter_label,
        d.month_name,
        d.month_num,
        d.week_of_year,
        d.is_weekend,
        d.month_year_label,
        round(
            (c.cancelled_bookings * 100.0) / nullif(c.total_bookings, 0),
            2
        )                                           as cancellation_rate_pct

    from combined c
    left join {{ ref('dim_date') }} d
        on c.date_id = d.date_id
)

select * from with_date
order by date_id, revenue_type
