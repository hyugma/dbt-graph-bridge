{{ config(
    materialized='node',
    labels=['Industry'],
    unique_key='industry'
) }}

SELECT DISTINCT
    industry
FROM {{ ref('stg_forbes_g2k') }}
WHERE industry IS NOT NULL
