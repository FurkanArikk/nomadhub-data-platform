{#- Shared cleaning helpers for RAW → STAGING. RAW is all VARCHAR, so typing lives here. -#}

{#- BTS flags are written as "1.00" / "0.00". Missing → NULL. -#}
{% macro bts_flag(column) -%}
    (try_to_number({{ column }}, 10, 2) = 1)
{%- endmacro %}

{#- BTS clock times are local "hhmm" strings ("0659", and "2400" for midnight). -#}
{% macro hhmm_to_time(column) -%}
    try_to_time(lpad(iff({{ column }} = '2400', '0000', {{ column }}), 4, '0'), 'HH24MI')
{%- endmacro %}

{#- One BTS flight = date + carrier + flight number + route + scheduled departure.
    Used by both stg_bts__flights and stg_app__flight_bookings, so the join key is
    built from identically normalised parts on both sides. -#}
{% macro flight_key(flight_date, airline, flight_number, origin, dest, crs_dep_time) -%}
    {{ dbt_utils.generate_surrogate_key([
        "try_to_date(" ~ flight_date ~ ")",
        "upper(trim(" ~ airline ~ "))",
        "try_to_number(" ~ flight_number ~ ")",
        "upper(trim(" ~ origin ~ "))",
        "upper(trim(" ~ dest ~ "))",
        "lpad(" ~ crs_dep_time ~ ", 4, '0')",
    ]) }}
{%- endmacro %}

{#- Inside Airbnb text: <br/> tags for line breaks and a few HTML entities. -#}
{% macro clean_html_text(column) -%}
    nullif(trim(
        replace(replace(replace(replace(replace(
            regexp_replace({{ column }}, '<br\\s*/?>', '\n', 1, 0, 'i'),
        '&amp;', '&'), '&quot;', '"'), '&#39;', ''''), '&lt;', '<'), '&gt;', '>')
    ), '')
{%- endmacro %}
