-- How full is each city over the next 12 months?
-- From the 188M-row Inside Airbnb calendar (latest snapshot). An unavailable night is
-- booked OR blocked by the host, so occupancy here is a proxy — an upper bound.
-- Grain: calendar month × city × room type.

select
    date_trunc(month, c.calendar_date)::date                    as month,
    c.city,
    l.room_type,
    min(c.snapshot_date)                                        as snapshot_date,
    count(distinct c.listing_id)                                as listings,
    count(*)                                                    as listing_nights,
    count_if(not c.is_available)                                as unavailable_nights,
    count_if(c.is_available)                                    as available_nights,
    round(div0(count_if(not c.is_available), count(*)), 4)      as occupancy_proxy,
    round(avg(c.minimum_nights), 1)                             as avg_minimum_nights
from {{ ref('stg_airbnb__calendar') }} c
left join {{ ref('dim_listings') }} l on l.listing_id = c.listing_id
group by all
