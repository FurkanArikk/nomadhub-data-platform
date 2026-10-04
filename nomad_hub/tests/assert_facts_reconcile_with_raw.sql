-- depends_on: {{ ref('stg_bts__flights') }}
-- depends_on: {{ ref('fct_flights') }}
-- depends_on: {{ ref('fct_stay_bookings') }}
-- depends_on: {{ ref('fct_flight_bookings') }}

-- Nothing is lost or duplicated between Bronze and Gold: every distinct id in RAW
-- reaches its fact table exactly once. Returns a row per table that doesn't reconcile.

with counts as (
    select 'flights' as tbl,
           (select count(*) from {{ ref('stg_bts__flights') }})                       as raw_ids,
           (select count(*) from {{ ref('fct_flights') }})                            as fact_rows
    union all
    select 'stay_bookings',
           (select count(distinct stay_booking_id) from {{ source('raw', 'stay_bookings') }}),
           (select count(*) from {{ ref('fct_stay_bookings') }})
    union all
    select 'flight_bookings',
           (select count(distinct flight_booking_id) from {{ source('raw', 'flight_bookings') }}),
           (select count(*) from {{ ref('fct_flight_bookings') }})
)

select * from counts where raw_ids != fact_rows
