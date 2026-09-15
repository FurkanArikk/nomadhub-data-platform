{% snapshot snap_hotels %}

{{
    config(
        target_database='NOMAD_HUB',
        target_schema='SNAPSHOTS',
        unique_key='hotel_id',
        strategy='check',
        check_cols=['star_rating', 'city', 'country_code', 'is_active'],
        invalidate_hard_deletes=True
    )
}}

select
    hotel_id,
    hotel_name,
    country_code,
    city,
    star_rating,
    is_active,
    created_at
from {{ ref('stg_hotels') }}

{% endsnapshot %}
