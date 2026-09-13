{{
    config(
        materialized        = 'incremental',
        incremental_strategy= 'merge',
        unique_key          = 'booking_id',
        cluster_by          = ['check_in_date'],
        on_schema_change    = 'sync_all_columns'
    )
}}

-- Gold: fct_hotel_bookings
-- Incremental hotel bookings fact table (MERGE on booking_id).

with bookings as (
    select * from {{ ref('stg_hotel_bookings') }}

    {% if is_incremental() %}
        where booking_date >= dateadd(
            'day',
            -{{ var('incremental_lookback_days', 3) }},
            (select max(booking_date) from {{ this }})
        )
    {% endif %}
),

dim_hotels as (
    select hotel_id, hotel_sk
    from {{ ref('dim_hotels') }}
),

dim_users as (
    select user_id, user_sk
    from {{ ref('dim_users') }}
),

enriched as (
    select
        b.booking_id,
        b.booking_ref,

        -- Dimension FK references
        coalesce(u.user_sk, 'unknown')      as user_sk,
        coalesce(h.hotel_sk, 'unknown')     as hotel_sk,
        b.booking_date                      as booking_date_id,
        b.check_in_date                     as check_in_date_id,
        b.check_out_date                    as check_out_date_id,

        -- Stay attributes
        b.room_type,
        b.num_nights,
        b.num_guests,
        b.num_rooms,

        -- Financials
        b.rate_per_night_usd,
        b.total_rate_usd,
        b.taxes_usd,
        b.total_amount_usd,
        b.room_revenue_usd,
        b.recognised_revenue_usd,

        -- Status & flags
        b.booking_status,
        b.is_cancelled,
        b.is_refundable,
        b.breakfast_included,
        b.airport_transfer,
        b.special_requests,
        b.payment_method,
        b.travel_purpose,

        -- Time attributes
        b.advance_booking_days,
        b.los_bucket,
        b.check_in_month,

        -- Metadata
        b.created_at

    from bookings b
    left join dim_hotels h on b.hotel_id = h.hotel_id
    left join dim_users u  on b.user_id  = u.user_id
)

select * from enriched
