{{ config(
    materialized='node',
    labels=['CEO', 'Person'],
    unique_key='ceoName'
) }}

SELECT DISTINCT
    ceoName
FROM {{ ref('stg_forbes_g2k') }}
WHERE ceoName IS NOT NULL
