-- Does a delayed arrival show up in the review?
-- Joins three real things: the guest's review (Inside Airbnb), the flight they were
-- booked on (BTS, with its actual arrival delay), and Gemini's reading of the review.
-- Grain: arrival delay bucket of the outbound flight.

with stays as (
    select
        s.stay_booking_id,
        s.review_id,
        f.arrival_status,
        f.arr_delay_min,
        case
            when f.is_cancelled then '5_cancelled'
            when f.is_diverted then '4_diverted'
            when f.arr_delay_min >= 180 then '3_delayed_3h_plus'
            when f.arr_delay_min >= 60 then '2_delayed_1_3h'
            when f.arr_delay_min >= 15 then '1_delayed_15_59m'
            else '0_on_time'
        end                                         as delay_bucket
    from {{ ref('fct_stay_bookings') }} s
    join {{ ref('fct_flight_bookings') }} b
      on b.stay_booking_id = s.stay_booking_id and b.leg = 'outbound'
    join {{ ref('fct_flights') }} f on f.flight_id = b.flight_id
    where not s.is_cancelled
)

select
    st.delay_bucket,
    count(*)                                                        as reviewed_stays,
    round(avg(st.arr_delay_min), 1)                                 as avg_arrival_delay_min,
    round(avg(e.sentiment_score), 3)                                as avg_sentiment_score,
    round(div0(count_if(e.sentiment = 'negative'), count(*)), 4)    as negative_share,
    round(div0(count_if(e.mentions_travel_disruption), count(*)), 4) as mentions_disruption_share
from stays st
join {{ source('ai', 'review_enrichments') }} e on e.review_id = st.review_id
group by st.delay_bucket
order by st.delay_bucket
