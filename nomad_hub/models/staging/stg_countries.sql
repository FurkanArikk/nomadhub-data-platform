-- Silver: stg_countries
-- Clean, rename, and type-cast the raw countries table.

with source as (
    select * from {{ source('raw', 'countries') }}
),

renamed as (
    select
        country_code,
        country_name,
        region,
        upper(currency_code)                    as currency_code,
        language,
        timezone,
        coalesce(visa_required, false)          as visa_required,
        cast(created_at as date)                as created_at
    from source
    where country_code is not null
      and country_name is not null
)

select * from renamed
