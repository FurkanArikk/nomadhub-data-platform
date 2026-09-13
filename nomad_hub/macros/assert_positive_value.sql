-- Macro: assert_positive_value
-- Custom generic test: asserts that a numeric column has no negative values.
-- Usage in schema.yml:
--   tests:
--     - nomad_hub.assert_positive_value

{% test assert_positive_value(model, column_name) %}

select
    {{ column_name }},
    count(*) as failing_rows
from {{ model }}
where {{ column_name }} < 0
group by 1
having count(*) > 0

{% endtest %}
