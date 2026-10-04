-- Platform users with derived demographics and their home metro (when they live near
-- one of the destination cities' airports, they never need a flight to get there).

with users as (
    select * from {{ ref('stg_app__users') }}
)

select
    u.user_id,
    u.first_name,
    u.last_name,
    u.email,
    u.gender,
    u.birth_date,
    datediff(year, u.birth_date, current_date())                  as age,
    case
        when datediff(year, u.birth_date, current_date()) < 25 then '18-24'
        when datediff(year, u.birth_date, current_date()) < 35 then '25-34'
        when datediff(year, u.birth_date, current_date()) < 45 then '35-44'
        when datediff(year, u.birth_date, current_date()) < 55 then '45-54'
        when datediff(year, u.birth_date, current_date()) < 65 then '55-64'
        else '65+'
    end                                                           as age_band,
    u.home_country_code,
    u.home_country_code = 'US'                                    as is_us_resident,
    u.home_airport,
    ha.city                                                       as home_nomad_city,
    u.preferred_language,
    u.signed_up_at,
    u.signed_up_at::date                                          as signup_date,
    u.acquisition_channel,
    u.marketing_opt_in
from users u
left join {{ ref('city_airports') }} ha on ha.iata_code = u.home_airport
