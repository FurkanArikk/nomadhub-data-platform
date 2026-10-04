-- 365-day forward availability per listing, from each city's latest snapshot.
-- available = false means booked OR blocked by the host; Inside Airbnb can't tell
-- the two apart, so downstream we call it an occupancy *proxy*.
-- ~188M rows: we keep only the latest snapshot per city with a join (cheaper than a
-- window over every row).

with source as (
    select * from {{ source('raw', 'calendar') }}
),

latest_snapshot as (
    select city, max(snapshot_date) as snapshot_date
    from source
    group by city
)

select
    try_to_number(s.listing_id)         as listing_id,
    s.city,
    try_to_date(s.snapshot_date)        as snapshot_date,
    try_to_date(s.calendar_date)        as calendar_date,
    try_to_boolean(s.available)         as is_available,
    try_to_number(s.minimum_nights)     as minimum_nights,
    try_to_number(s.maximum_nights)     as maximum_nights,
    s._loaded_at
from source s
join latest_snapshot l
  on l.city = s.city
 and l.snapshot_date = s.snapshot_date
