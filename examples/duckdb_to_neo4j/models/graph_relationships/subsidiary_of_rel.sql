{{ config(
    materialized='relationship',
    relationship_type='SUBSIDIARY_OF',
    source_node={
        'labels': ['Company'],
        'key': 'company_id',
        'column': 'company_id'
    },
    target_node={
        'labels': ['Company'],
        'key': 'company_id',
        'column': 'parent_company_id'
    }
) }}
-- depends_on: {{ ref('company_node') }}
-- depends_on: {{ ref('company_node') }}


SELECT
    company_id,
    parent_company_id
FROM {{ ref('stg_forbes_g2k') }}
WHERE company_id IS NOT NULL AND parent_company_id IS NOT NULL
