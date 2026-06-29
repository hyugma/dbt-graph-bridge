{{ config(
    materialized='relationship',
    relationship_type='LOCATED_IN',
    source_node={
        'labels': ['City'],
        'key': 'city',
        'column': 'city'
    },
    target_node={
        'labels': ['Country'],
        'key': 'country',
        'column': 'country'
    }
) }}
-- depends_on: {{ ref('city_node') }}
-- depends_on: {{ ref('country_node') }}

SELECT DISTINCT
    city,
    country
FROM stg_companies
WHERE city IS NOT NULL AND country IS NOT NULL
