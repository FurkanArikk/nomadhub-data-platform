-- Gold: mart_user_cohort
-- ✨ NEW: Monthly registration cohort analysis.
-- Tracks each cohort's booking behaviour over their lifetime.
-- Powers the "User Cohort" retention chart in Streamlit.

with user_cohorts as (
    select
        user_id,
        user_sk,
        loyalty_tier,
        loyalty_tier_rank,
        age_group,
        region,
        date_trunc('month', registration_date)      as cohort_month
    from {{ ref('dim_users') }}
),

flight_activity as (
    select
        u.user_id,
        u.cohort_month,
        date_trunc('month', f.booking_date_id)      as activity_month,
        datediff(
            'month',
            u.cohort_month,
            date_trunc('month', f.booking_date_id)
        )                                           as months_since_registration,

        count(f.flight_id)                          as flight_bookings,
        sum(f.recognised_revenue_usd)               as flight_revenue_usd

    from user_cohorts u
    inner join {{ ref('fct_flights') }} f
        on u.user_sk = f.user_sk
    where f.booking_status != 'cancelled'
    group by 1, 2, 3, 4
),

hotel_activity as (
    select
        u.user_id,
        u.cohort_month,
        date_trunc('month', b.booking_date_id)      as activity_month,
        datediff(
            'month',
            u.cohort_month,
            date_trunc('month', b.booking_date_id)
        )                                           as months_since_registration,

        count(b.booking_id)                         as hotel_bookings,
        sum(b.recognised_revenue_usd)               as hotel_revenue_usd

    from user_cohorts u
    inner join {{ ref('fct_hotel_bookings') }} b
        on u.user_sk = b.user_sk
    where b.booking_status != 'cancelled'
    group by 1, 2, 3, 4
),

combined as (
    select
        coalesce(f.user_id, h.user_id)              as user_id,
        coalesce(f.cohort_month, h.cohort_month)    as cohort_month,
        coalesce(f.activity_month, h.activity_month) as activity_month,
        coalesce(f.months_since_registration,
                 h.months_since_registration)        as months_since_registration,
        coalesce(f.flight_bookings, 0)              as flight_bookings,
        coalesce(h.hotel_bookings, 0)               as hotel_bookings,
        coalesce(f.flight_revenue_usd, 0)           as flight_revenue_usd,
        coalesce(h.hotel_revenue_usd, 0)            as hotel_revenue_usd

    from flight_activity f
    full outer join hotel_activity h
        on f.user_id        = h.user_id
       and f.cohort_month   = h.cohort_month
       and f.activity_month = h.activity_month
),

with_cohort_size as (
    select
        c.*,
        uc.loyalty_tier,
        uc.loyalty_tier_rank,
        uc.age_group,
        uc.region,
        (c.flight_bookings + c.hotel_bookings)      as total_bookings,
        (c.flight_revenue_usd + c.hotel_revenue_usd) as total_revenue_usd,

        -- Cohort size for retention calculation
        count(distinct c.user_id) over (
            partition by c.cohort_month
        )                                           as cohort_size

    from combined c
    left join user_cohorts uc
        on c.user_id = uc.user_id
)

select * from with_cohort_size
order by cohort_month, activity_month
