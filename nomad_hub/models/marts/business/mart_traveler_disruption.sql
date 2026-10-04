-- How often are NomadHub travellers' trips disrupted by the airline they flew?
-- Joins every booked leg to the REAL outcome of that flight in BTS.
-- Grain: flight month × airline × leg (outbound/return).

select
    date_trunc(month, b.flight_date)::date                                  as month,
    b.airline_code,
    a.airline_name,
    b.leg,

    count(*)                                                                as legs_booked,
    sum(b.passengers)                                                       as passengers,
    round(sum(b.total_fare_usd), 2)                                         as fares_usd,

    count_if(f.is_cancelled)                                                as legs_on_cancelled_flights,
    count_if(f.is_diverted)                                                 as legs_on_diverted_flights,
    count_if(f.arr_delay_min >= 15)                                         as legs_arrived_15_plus_late,
    count_if(f.arr_delay_min >= 60)                                         as legs_arrived_60_plus_late,
    count_if(f.arr_delay_min >= 180)                                        as legs_arrived_3h_plus_late,

    sum(iff(f.is_cancelled or f.arr_delay_min >= 60, b.passengers, 0))      as passengers_disrupted,
    round(div0(count_if(f.is_cancelled or f.is_diverted or f.arr_delay_min >= 60),
               count(*)), 4)                                                as disruption_rate,
    round(avg(iff(f.arr_delay_min > 0, f.arr_delay_min, null)), 1)          as avg_delay_when_late_min
from {{ ref('fct_flight_bookings') }} b
join {{ ref('fct_flights') }} f   on f.flight_id = b.flight_id
left join {{ ref('dim_airlines') }} a on a.airline_code = b.airline_code
group by all
