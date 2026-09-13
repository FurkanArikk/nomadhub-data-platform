-- Macro: generate_schema_name
-- Routes dbt models to the correct Snowflake schema based on the
-- custom_schema_name config (set in dbt_project.yml via +schema).
-- Without this macro, dbt would prefix the schema name with the profile target schema.

{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema | upper }}
    {%- else -%}
        {{ custom_schema_name | upper }}
    {%- endif -%}
{%- endmacro %}
