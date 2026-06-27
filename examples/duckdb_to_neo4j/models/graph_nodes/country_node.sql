{{ config(
    materialized='node',
    labels=['Country'],
    unique_key='country'
) }}

SELECT DISTINCT
    country
FROM {{ ref('stg_forbes_g2k') }}
WHERE country IS NOT NULL
