-- One row per operated (or cancelled) US domestic flight.
-- BTS times are local clock times "hhmm"; we combine them with the flight date and
-- derive actual times from the scheduled time + reported delay, which avoids the
-- after-midnight ambiguity of the raw actual-time columns.

with source as (
    select * from {{ source('raw', 'flights') }}
),

typed as (
    select
        {{ flight_key('flight_date', 'reporting_airline', 'flight_number', 'origin', 'dest', 'crs_dep_time') }}
                                                        as flight_id,
        try_to_date(flight_date)                        as flight_date,
        upper(trim(reporting_airline))                  as airline_code,
        try_to_number(flight_number)                    as flight_number,
        nullif(trim(tail_number), '')                   as tail_number,

        upper(trim(origin))                             as origin_airport,
        origin_city_name,
        origin_state,
        upper(trim(dest))                               as dest_airport,
        dest_city_name,
        dest_state,
        try_to_number(distance, 10, 2)::int             as distance_miles,

        {{ hhmm_to_time('crs_dep_time') }}              as scheduled_dep_time,
        {{ hhmm_to_time('crs_arr_time') }}              as scheduled_arr_time,
        try_to_number(dep_delay, 10, 2)::int            as dep_delay_min,
        try_to_number(arr_delay, 10, 2)::int            as arr_delay_min,
        try_to_number(taxi_out, 10, 2)::int             as taxi_out_min,
        try_to_number(taxi_in, 10, 2)::int              as taxi_in_min,
        try_to_number(crs_elapsed_time, 10, 2)::int     as scheduled_elapsed_min,
        try_to_number(actual_elapsed_time, 10, 2)::int  as actual_elapsed_min,
        try_to_number(air_time, 10, 2)::int             as air_time_min,

        coalesce({{ bts_flag('cancelled') }}, false)    as is_cancelled,
        coalesce({{ bts_flag('diverted') }}, false)     as is_diverted,
        coalesce({{ bts_flag('dep_del15') }}, false)    as is_dep_delayed_15,
        coalesce({{ bts_flag('arr_del15') }}, false)    as is_arr_delayed_15,
        decode(cancellation_code,
               'A', 'carrier', 'B', 'weather', 'C', 'national_air_system', 'D', 'security')
                                                        as cancellation_reason,

        -- Minutes of arrival delay attributed to each cause (only for 15+ min delays)
        try_to_number(carrier_delay, 10, 2)::int        as carrier_delay_min,
        try_to_number(weather_delay, 10, 2)::int        as weather_delay_min,
        try_to_number(nas_delay, 10, 2)::int            as nas_delay_min,
        try_to_number(security_delay, 10, 2)::int       as security_delay_min,
        try_to_number(late_aircraft_delay, 10, 2)::int  as late_aircraft_delay_min,

        _source_file,
        _loaded_at
    from source
),

final as (
    select
        *,
        timestamp_ntz_from_parts(flight_date, scheduled_dep_time)          as scheduled_departure_at,
        timestamp_ntz_from_parts(
            dateadd(day, iff(scheduled_arr_time < scheduled_dep_time, 1, 0), flight_date),
            scheduled_arr_time)                                             as scheduled_arrival_at,
        case
            when is_cancelled then 'cancelled'
            when is_diverted then 'diverted'
            when arr_delay_min >= 15 then 'delayed'
            else 'on_time'
        end                                                                 as arrival_status
    from typed
)

select
    *,
    dateadd(minute, dep_delay_min, scheduled_departure_at) as actual_departure_at,
    dateadd(minute, arr_delay_min, scheduled_arrival_at)   as actual_arrival_at
from final
qualify row_number() over (partition by flight_id order by _loaded_at desc) = 1
