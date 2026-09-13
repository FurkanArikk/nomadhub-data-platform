-- Gold: mart_destination_performance
-- ✨ NEW: Ranks destinations by flight volume, revenue, avg rating.
-- Powers the "Flight Analytics" destination leaderboard in Streamlit.

with flight_dest as (
    select
        d.iata_code,
        d.city                              as destination_city,
        d.country_name                      as destination_country,
        d.region                            as destination_region,
        d.latitude,
        d.longitude,
        d.is_international,

        count(f.flight_id)                  as total_inbound_flights,
        sum(f.recognised_revenue_usd)       as total_revenue_usd,
        avg(f.total_fare_usd)               as avg_fare_usd,
        sum(f.num_passengers)               as total_passengers,
        avg(f.advance_booking_days)         as avg_advance_booking_days,
        sum(case when f.is_cancelled then 1 else 0 end) as cancelled_flights,
        round(
            sum(case when f.is_cancelled then 1 else 0 end) * 100.0
            / nullif(count(f.flight_id), 0),
            2
        )                                   as cancellation_rate_pct,

        -- Top cabin class for this destination
        mode(f.cabin_class)                 as most_popular_cabin,
        mode(f.travel_purpose)              as most_popular_purpose

    from {{ ref('fct_flights') }} f
    inner join {{ ref('dim_destinations') }} d
        on f.dest_destination_sk = d.destination_sk
    where f.booking_status != 'cancelled'
    group by 1, 2, 3, 4, 5, 6, 7
),

hotel_dest as (
    select
        h.country_name                      as destination_country,
        h.city                              as destination_city,
        count(b.booking_id)                 as total_hotel_bookings,
        avg(b.num_nights)                   as avg_stay_nights,
        avg(b.rate_per_night_usd)           as avg_nightly_rate_usd
    from {{ ref('fct_hotel_bookings') }} b
    inner join {{ ref('dim_hotels') }} h
        on b.hotel_sk = h.hotel_sk
    where b.booking_status != 'cancelled'
    group by 1, 2
),

joined as (
    select
        f.*,
        coalesce(h.total_hotel_bookings, 0) as total_hotel_bookings,
        coalesce(h.avg_stay_nights, 0)      as avg_stay_nights,
        coalesce(h.avg_nightly_rate_usd, 0) as avg_nightly_rate_usd,

        -- Popularity score (composite)
        round(
            (f.total_inbound_flights * 0.4)
            + (f.total_revenue_usd / 1000.0 * 0.4)
            + (coalesce(h.total_hotel_bookings, 0) * 0.2),
            0
        )                                   as popularity_score,

        -- Revenue rank
        row_number() over (order by f.total_revenue_usd desc)          as revenue_rank,
        row_number() over (order by f.total_inbound_flights desc)       as volume_rank

    from flight_dest f
    left join hotel_dest h
        on f.destination_city    = h.destination_city
       and f.destination_country = h.destination_country
)

select * from joined
order by revenue_rank
