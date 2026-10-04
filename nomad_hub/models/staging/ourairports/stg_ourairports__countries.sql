with source as (
    select * from {{ source('raw', 'countries') }}
)

select
    code        as country_code,
    name        as country_name,
    continent,
    _loaded_at
from source
qualify row_number() over (partition by code order by _loaded_at desc) = 1
