{{ config(
    materialized='node',
    labels=['Industry'],
    unique_key='industry'
) }}
{% if var('docs_lineage', false) %}
-- depends_on: {{ ref('stg_companies') }}
{% endif %}

SELECT DISTINCT
    industry
FROM stg_companies
WHERE industry IS NOT NULL
