{{ config(
    materialized='relationship',
    relationship_type='LED_BY',
    source_node={
        'labels': ['Company'],
        'key': 'company_id',
        'column': 'company_id'
    },
    target_node={
        'labels': ['CEO'],
        'key': 'ceo_name',
        'column': 'ceo_name'
    }
) }}
-- depends_on: {{ ref('company_node') }}
-- depends_on: {{ ref('ceo_node') }}

SELECT
    company_id,
    ceo_name,
    ceo_title
FROM stg_companies
WHERE company_id IS NOT NULL AND ceo_name IS NOT NULL
