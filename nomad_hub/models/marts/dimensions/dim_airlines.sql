-- BTS reporting carriers with their activity window in the data.

with activity as (
    select
        airline_code,
        min(flight_date)    as first_flight_date,
        max(flight_date)    as last_flight_date,
        count(*)            as flights
    from {{ ref('stg_bts__flights') }}
    group by airline_code
)

select
    a.airline_code,
    a.airline_name,
    a.carrier_type,
    a.parent_airline_code,
    p.airline_name          as parent_airline_name,
    act.first_flight_date,
    act.last_flight_date,
    coalesce(act.flights, 0) as flights
from {{ ref('airlines') }} a
left join {{ ref('airlines') }} p on p.airline_code = a.parent_airline_code
left join activity act on act.airline_code = a.airline_code
