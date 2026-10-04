{{ config(
    unique_key='flight_id',
    cluster_by=['flight_date']
) }}

-- One row per US domestic flight, 2019–2025 (~45.8M). Incremental on _loaded_at:
-- a new monthly BTS file loaded by COPY INTO is the only thing a re-run processes.

select
    flight_id,
    flight_date,
    airline_code,
    flight_number,
    tail_number,
    origin_airport,
    dest_airport,
    distance_miles,
    scheduled_departure_at,
    scheduled_arrival_at,
    actual_departure_at,
    actual_arrival_at,
    hour(scheduled_departure_at)    as scheduled_dep_hour,
    dep_delay_min,
    arr_delay_min,
    taxi_out_min,
    taxi_in_min,
    scheduled_elapsed_min,
    actual_elapsed_min,
    air_time_min,
    arrival_status,
    is_cancelled,
    is_diverted,
    is_dep_delayed_15,
    is_arr_delayed_15,
    cancellation_reason,
    carrier_delay_min,
    weather_delay_min,
    nas_delay_min,
    security_delay_min,
    late_aircraft_delay_min,
    _loaded_at
from {{ ref('stg_bts__flights') }}
{% if is_incremental() %}
where _loaded_at > (select coalesce(max(_loaded_at), '1900-01-01'::timestamp_ltz) from {{ this }})
{% endif %}
