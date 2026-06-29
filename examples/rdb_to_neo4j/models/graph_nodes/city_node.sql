{{ config(
    materialized='node',
    labels=['City'],
    unique_key='city'
) }}
{% if var('docs_lineage', false) %}
-- depends_on: {{ ref('stg_companies') }}
{% endif %}

SELECT
    city,
    MAX(state) AS state
FROM stg_companies
WHERE city IS NOT NULL
GROUP BY city
