{{ config(
    materialized='node',
    labels=['Country'],
    unique_key='country'
) }}
{% if var('docs_lineage', false) %}
-- depends_on: {{ ref('stg_companies') }}
{% endif %}

SELECT DISTINCT
    country
FROM stg_companies
WHERE country IS NOT NULL
