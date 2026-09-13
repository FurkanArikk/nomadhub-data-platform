-- Gold: dim_date
-- Date dimension generated via dbt_utils.date_spine.
-- Covers 2021-01-01 to current_date + 365 days (future bookings).
-- One row per calendar day; used as the primary time axis across all fact joins.

{{ config(materialized='table') }}

with date_spine as (
    {{
        dbt_utils.date_spine(
            datepart="day",
            start_date="cast('" ~ var('date_spine_start') ~ "' as date)",
            end_date="dateadd(day, 365, current_date())"
        )
    }}
),

dates as (
    select
        cast(date_day as date)                              as date_id,

        -- Year / Quarter / Month / Week
        year(date_day)                                      as year,
        quarter(date_day)                                   as quarter_num,
        'Q' || quarter(date_day)                            as quarter_label,
        month(date_day)                                     as month_num,
        monthname(date_day)                                 as month_name,
        left(monthname(date_day), 3)                        as month_name_short,
        weekofyear(date_day)                                as week_of_year,
        dayofweek(date_day)                                 as day_of_week_num,  -- 0=Mon, 6=Sun
        dayname(date_day)                                   as day_of_week_name,
        left(dayname(date_day), 3)                          as day_of_week_short,
        dayofmonth(date_day)                                as day_of_month,
        dayofyear(date_day)                                 as day_of_year,

        -- Fiscal year (April start — common in travel industry)
        case
            when month(date_day) >= 4
            then year(date_day)
            else year(date_day) - 1
        end                                                 as fiscal_year,

        -- Boolean flags
        (dayofweek(date_day) in (0, 6))                     as is_weekend,
        (dayofweek(date_day) not in (0, 6))                 as is_weekday,
        (date_day = last_day(date_day))                     as is_last_day_of_month,
        (date_day <= current_date())                        as is_past_or_today,
        (date_day > current_date())                         as is_future,

        -- Month / Quarter truncates
        date_trunc('month', date_day)                       as month_start_date,
        date_trunc('quarter', date_day)                     as quarter_start_date,
        date_trunc('year', date_day)                        as year_start_date,

        -- 12-char label for display
        to_char(date_day, 'YYYY-MM-DD')                     as date_label,
        to_char(date_day, 'Mon YYYY')                       as month_year_label

    from date_spine
)

select * from dates
order by date_id
