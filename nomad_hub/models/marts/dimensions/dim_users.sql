-- Gold: dim_users
-- Enriched user dimension. Joins to countries for full geographic context.
-- PII columns (email, phone) are present for NOMAD_ADMIN / DBT_ROLE.
-- ANALYST_ROLE access is masked via Snowflake masking policy (06_row_access_policies.sql).

with users as (
    select * from {{ ref('stg_users') }}
    where is_active = true
),

countries as (
    select * from {{ ref('stg_countries') }}
),

joined as (
    select
        -- Surrogate key
        {{ dbt_utils.generate_surrogate_key(['u.user_id']) }} as user_sk,

        -- Natural key
        u.user_id,

        -- Identity (PII — masked for analysts at Snowflake layer)
        u.username,
        u.email,
        u.first_name,
        u.last_name,
        u.phone,

        -- Demographics
        u.date_of_birth,
        u.age_years,
        u.age_group,
        u.gender,

        -- Geography
        u.country_code,
        coalesce(c.country_name, 'Unknown')         as country_name,
        coalesce(c.region, 'Unknown')               as region,
        u.city,
        c.currency_code                             as home_currency,
        c.timezone                                  as home_timezone,

        -- Loyalty
        u.loyalty_tier,
        u.loyalty_points,

        -- Preferences
        u.preferred_cabin,
        u.preferred_hotel_category,
        u.newsletter_subscribed,

        -- Engagement
        u.registration_date,
        u.last_login_date,
        u.tenure_days,
        u.is_active,

        -- Derived: loyalty tier rank (for sorting/ordering)
        case u.loyalty_tier
            when 'Platinum' then 4
            when 'Gold'     then 3
            when 'Silver'   then 2
            else 1
        end                                         as loyalty_tier_rank,

        -- Metadata
        u.created_at

    from users u
    left join countries c
        on u.country_code = c.country_code
)

select * from joined
