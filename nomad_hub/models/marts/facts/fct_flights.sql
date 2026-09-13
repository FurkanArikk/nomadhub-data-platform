{{
    config(
        materialized        = 'incremental',
        incremental_strategy= 'merge',
        unique_key          = 'flight_id',
        cluster_by          = ['booking_date'],
        on_schema_change    = 'sync_all_columns'
    )
}}

-- Gold: fct_flights
-- Incremental flight fact table (MERGE on flight_id).
-- Joins staging flights to dimension surrogate keys.
-- Incremental filter: re-processes last N days to catch late updates.

with flights as (
    select * from {{ ref('stg_flights') }}

    {% if is_incremental() %}
        where booking_date >= dateadd(
            'day',
            -{{ var('incremental_lookback_days', 3) }},
            (select max(booking_date) from {{ this }})
        )
    {% endif %}
),

dim_dest as (
    select iata_code, destination_sk
    from {{ ref('dim_destinations') }}
),

dim_users as (
    select user_id, user_sk
    from {{ ref('dim_users') }}
),

enriched as (
    select
        f.flight_id,
        f.booking_ref,

        -- Dimension FK references
        coalesce(u.user_sk, 'unknown')          as user_sk,
        coalesce(o.destination_sk, 'unknown')   as origin_destination_sk,
        coalesce(d.destination_sk, 'unknown')   as dest_destination_sk,
        f.booking_date                          as booking_date_id,
        f.outbound_date                         as outbound_date_id,
        f.return_date                           as return_date_id,

        -- Booking attributes
        f.airline,
        f.flight_number,
        f.cabin_class,
        f.is_round_trip,
        f.num_passengers,
        f.checked_bags,

        -- Financials
        f.base_fare_usd,
        f.taxes_usd,
        f.total_fare_usd,
        f.fare_per_passenger_usd,
        f.recognised_revenue_usd,

        -- Status & flags
        f.booking_status,
        f.is_cancelled,
        f.is_refundable,
        f.payment_method,
        f.travel_purpose,

        -- Time attributes
        f.advance_booking_days,
        f.lead_time_bucket,
        f.booking_month,

        -- Metadata
        f.created_at

    from flights f
    left join dim_dest o  on f.origin_iata      = o.iata_code
    left join dim_dest d  on f.destination_iata = d.iata_code
    left join dim_users u on f.user_id          = u.user_id
)

select * from enriched
