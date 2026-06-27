{{ config(
    materialized='node',
    labels=['Company'],
    unique_key='company_id',
    indexes=[
        {'properties': ['company_name']},
        {'properties': ['rank']}
    ]
) }}

SELECT
    company_id,
    company_name,
    rank,
    revenue,
    profits,
    assets,
    marketValue,
    employees,
    yearFounded,
    description,
    webSite
FROM {{ ref('stg_forbes_g2k') }}
WHERE company_id IS NOT NULL
