-- Do travellers come back? Cohort = month of a user's first booking.
-- Grain: cohort month × months since first booking.
-- Users are real reviewers, so repeat behaviour here is real Airbnb repeat behaviour.

with bookings as (
    select
        user_id,
        date_trunc(month, booked_at)::date  as booking_month,
        is_cancelled,
        total_amount_usd
    from {{ ref('fct_stay_bookings') }}
),

first_booking as (
    select user_id, min(booking_month) as cohort_month
    from bookings
    group by user_id
),

cohort_size as (
    select cohort_month, count(*) as cohort_users
    from first_booking
    group by cohort_month
),

activity as (
    select
        f.cohort_month,
        datediff(month, f.cohort_month, b.booking_month)                as months_since_first_booking,
        count(distinct b.user_id)                                       as active_users,
        count(*)                                                        as bookings,
        round(sum(iff(not b.is_cancelled, b.total_amount_usd, 0)), 2)   as gross_booking_value_usd
    from bookings b
    join first_booking f using (user_id)
    group by all
)

select
    a.cohort_month,
    a.months_since_first_booking,
    s.cohort_users,
    a.active_users,
    round(a.active_users / s.cohort_users, 4)    as retention_rate,
    a.bookings,
    a.gross_booking_value_usd
from activity a
join cohort_size s using (cohort_month)
