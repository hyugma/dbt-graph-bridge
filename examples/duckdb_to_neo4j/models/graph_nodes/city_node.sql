{{ config(
    materialized='node',
    labels=['City'],
    unique_key='city'
) }}

SELECT DISTINCT
    city,
    MAX(state) AS state
FROM {{ ref('stg_forbes_g2k') }}
WHERE city IS NOT NULL
GROUP BY city
