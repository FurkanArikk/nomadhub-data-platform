-- Real guest reviews (free text, many languages). Every snapshot repeats the whole
-- history, so we keep one row per review_id. Reviewer names were dropped at download;
-- reviewer_id links to stg_app__users.source_reviewer_id.

with source as (
    select * from {{ source('raw', 'reviews') }}
)

select
    try_to_number(review_id)                as review_id,
    try_to_number(listing_id)               as listing_id,
    city,
    try_to_date(review_date)                as review_date,
    try_to_number(reviewer_id)              as reviewer_id,
    {{ clean_html_text('comments') }}       as comment_text,
    length({{ clean_html_text('comments') }}) as comment_length,
    try_to_date(snapshot_date)              as snapshot_date,
    _loaded_at
from source
where try_to_number(review_id) is not null
qualify row_number() over (
    partition by try_to_number(review_id)
    order by try_to_date(snapshot_date) desc, _loaded_at desc
) = 1
