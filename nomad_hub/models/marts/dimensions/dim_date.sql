-- Calendar from the first user signup to the end of the forward Airbnb calendar.

with spine as (
    {{ dbt_utils.date_spine(
        datepart="day",
        start_date="'" ~ var('date_spine_start') ~ "'::date",
        end_date="dateadd(day, 1, '" ~ var('date_spine_end') ~ "'::date)"
    ) }}
)

select
    date_day::date                              as date_day,
    year(date_day)                              as year,
    quarter(date_day)                           as quarter,
    month(date_day)                             as month,
    monthname(date_day)                         as month_name,
    to_char(date_day, 'YYYY-MM')                as year_month,
    date_trunc(month, date_day)::date           as month_start,
    date_trunc(week, date_day)::date            as week_start,
    dayofweekiso(date_day)                      as day_of_week_iso,   -- 1 = Monday
    dayname(date_day)                           as day_name,
    dayofweekiso(date_day) in (6, 7)            as is_weekend,
    case when month(date_day) in (12, 1, 2) then 'winter'
         when month(date_day) in (3, 4, 5)  then 'spring'
         when month(date_day) in (6, 7, 8)  then 'summer'
         else 'autumn' end                      as season_northern
from spine
