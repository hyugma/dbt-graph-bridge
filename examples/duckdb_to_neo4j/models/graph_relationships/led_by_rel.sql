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
        'key': 'ceoName',
        'column': 'ceoName'
    }
) }}
-- depends_on: {{ ref('company_node') }}
-- depends_on: {{ ref('ceo_node') }}


SELECT
    company_id,
    ceoName,
    ceoTitle
FROM {{ ref('stg_forbes_g2k') }}
WHERE company_id IS NOT NULL AND ceoName IS NOT NULL
