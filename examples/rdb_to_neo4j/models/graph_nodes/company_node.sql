{{ config(
    materialized='node',
    labels=['Company'],
    unique_key='company_id',
    indexes=[
        {'properties': ['company_name']},
        {'properties': ['rank']}
    ]
) }}
{% if var('docs_lineage', false) %}
-- depends_on: {{ ref('stg_companies') }}
{% endif %}

SELECT
    company_id,
    company_name,
    rank,
    revenue,
    profits,
    assets,
    market_value,
    employees,
    year_founded,
    description,
    web_site
FROM stg_companies
WHERE company_id IS NOT NULL
