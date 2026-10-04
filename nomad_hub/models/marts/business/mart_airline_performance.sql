-- How reliable is each airline, at each airport, each month?
-- Grain: month × airline × origin airport. Covers the 2020 collapse and the recovery.
-- on_time_rate follows the DOT definition: arrived < 15 min late, out of flights that
-- were neither cancelled nor diverted.

select
    date_trunc(month, f.flight_date)::date                          as month,
    f.airline_code,
    a.airline_name,
    a.carrier_type,
    f.origin_airport,
    ap.airport_name                                                 as origin_airport_name,
    ap.region_code                                                  as origin_state,

    count(*)                                                        as scheduled_flights,
    count_if(f.is_cancelled)                                        as cancelled_flights,
    count_if(f.is_diverted)                                         as diverted_flights,
    count_if(f.arrival_status = 'on_time')                          as on_time_flights,
    count_if(f.arrival_status = 'delayed')                          as delayed_flights,
    count_if(f.arr_delay_min >= 60)                                 as delayed_60_plus_flights,

    round(div0(count_if(f.arrival_status = 'on_time'),
               count_if(not f.is_cancelled and not f.is_diverted)), 4) as on_time_rate,
    round(div0(count_if(f.is_cancelled), count(*)), 4)              as cancellation_rate,
    round(avg(iff(f.arr_delay_min > 0, f.arr_delay_min, null)), 1)  as avg_arrival_delay_when_late_min,
    round(avg(f.dep_delay_min), 1)                                  as avg_departure_delay_min,
    round(avg(f.taxi_out_min), 1)                                   as avg_taxi_out_min,

    -- Where the delay minutes come from (BTS cause attribution, 15+ min delays only)
    sum(f.carrier_delay_min)                                        as carrier_delay_min,
    sum(f.weather_delay_min)                                        as weather_delay_min,
    sum(f.nas_delay_min)                                            as nas_delay_min,
    sum(f.security_delay_min)                                       as security_delay_min,
    sum(f.late_aircraft_delay_min)                                  as late_aircraft_delay_min,

    count_if(f.cancellation_reason = 'carrier')                     as cancelled_carrier,
    count_if(f.cancellation_reason = 'weather')                     as cancelled_weather,
    count_if(f.cancellation_reason = 'national_air_system')         as cancelled_nas,
    count_if(f.cancellation_reason = 'security')                    as cancelled_security
from {{ ref('fct_flights') }} f
left join {{ ref('dim_airlines') }} a  on a.airline_code = f.airline_code
left join {{ ref('dim_airports') }} ap on ap.iata_code = f.origin_airport
group by all
