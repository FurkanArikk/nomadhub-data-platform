-- Silver: stg_users
-- Clean user profiles, derive age group and tenure in days.

with source as (
    select * from {{ source('raw', 'users') }}
),

cleaned as (
    select
        user_id,
        lower(trim(username))               as username,
        lower(trim(email))                  as email,
        initcap(trim(first_name))           as first_name,
        initcap(trim(last_name))            as last_name,
        cast(date_of_birth as date)         as date_of_birth,
        gender,
        upper(country_code)                 as country_code,
        trim(city)                          as city,
        trim(phone)                         as phone,
        loyalty_tier,
        cast(loyalty_points as int)         as loyalty_points,
        preferred_cabin,
        preferred_hotel_category,
        coalesce(newsletter_subscribed, false) as newsletter_subscribed,
        cast(registration_date as date)     as registration_date,
        cast(last_login_date as date)       as last_login_date,
        coalesce(is_active, true)           as is_active,
        cast(created_at as date)            as created_at,

        -- Derived: age in years
        datediff('year', cast(date_of_birth as date), current_date()) as age_years,

        -- Derived: age group
        case
            when datediff('year', cast(date_of_birth as date), current_date()) < 25 then '18-24'
            when datediff('year', cast(date_of_birth as date), current_date()) < 35 then '25-34'
            when datediff('year', cast(date_of_birth as date), current_date()) < 45 then '35-44'
            when datediff('year', cast(date_of_birth as date), current_date()) < 55 then '45-54'
            when datediff('year', cast(date_of_birth as date), current_date()) < 65 then '55-64'
            else '65+'
        end                                 as age_group,

        -- Derived: account tenure days
        datediff('day', cast(registration_date as date), current_date()) as tenure_days

    from source
    where user_id is not null
      and email is not null
)

select * from cleaned
