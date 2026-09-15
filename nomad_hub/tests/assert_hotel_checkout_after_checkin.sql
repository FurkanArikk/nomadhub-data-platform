-- Custom Singular Test: Hotel check-out date must always be greater than check-in date
select
    booking_id,
    check_in_date,
    check_out_date
from {{ ref('fct_hotel_bookings') }}
where check_out_date <= check_in_date
