{{ config(
    materialized='node',
    labels=['CEO', 'Person'],
    unique_key='ceo_name'
) }}
{% if var('docs_lineage', false) %}
-- depends_on: {{ ref('stg_companies') }}
{% endif %}

SELECT DISTINCT
    ceo_name
FROM stg_companies
WHERE ceo_name IS NOT NULL
