-- Platform users (synthetic, one per real reviewer — see data/generate_data.py).

with source as (
    select * from {{ source('raw', 'users') }}
)

select
    try_to_number(user_id)                  as user_id,
    try_to_number(source_reviewer_id)       as source_reviewer_id,
    first_name,
    last_name,
    lower(email)                            as email,
    gender,
    try_to_date(birth_date)                 as birth_date,
    home_country_code,
    nullif(home_airport, '')                as home_airport,
    preferred_language,
    try_to_timestamp_ntz(signed_up_at)      as signed_up_at,
    acquisition_channel,
    try_to_boolean(marketing_opt_in)        as marketing_opt_in,
    _loaded_at
from source
qualify row_number() over (partition by try_to_number(user_id) order by _loaded_at desc) = 1
