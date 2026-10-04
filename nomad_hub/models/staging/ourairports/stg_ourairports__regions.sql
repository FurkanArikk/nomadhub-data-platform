with source as (
    select * from {{ source('raw', 'regions') }}
)

select
    code            as region_code,
    local_code,
    name            as region_name,
    iso_country     as country_code,
    _loaded_at
from source
qualify row_number() over (partition by code order by _loaded_at desc) = 1
