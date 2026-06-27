{{ config(
    materialized='relationship',
    relationship_type='HEADQUARTERED_IN',
    source_node={
        'labels': ['Company'],
        'key': 'company_id',
        'column': 'company_id'
    },
    target_node={
        'labels': ['City'],
        'key': 'city',
        'column': 'city'
    }
) }}
-- depends_on: {{ ref('company_node') }}
-- depends_on: {{ ref('city_node') }}


SELECT
    company_id,
    city
FROM {{ ref('stg_forbes_g2k') }}
WHERE company_id IS NOT NULL AND city IS NOT NULL
