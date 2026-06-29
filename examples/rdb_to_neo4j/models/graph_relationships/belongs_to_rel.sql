{{ config(
    materialized='relationship',
    relationship_type='BELONGS_TO',
    source_node={
        'labels': ['Company'],
        'key': 'company_id',
        'column': 'company_id'
    },
    target_node={
        'labels': ['Industry'],
        'key': 'industry',
        'column': 'industry'
    }
) }}
-- depends_on: {{ ref('company_node') }}
-- depends_on: {{ ref('industry_node') }}

SELECT
    company_id,
    industry
FROM stg_companies
WHERE company_id IS NOT NULL AND industry IS NOT NULL
