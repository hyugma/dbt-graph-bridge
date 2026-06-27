{{ config(
    materialized='node',
    labels=['Person', 'Employee'],
    unique_key='employee_id',
    indexes=[
        {'properties': ['name']}
    ]
) }}

SELECT
    employee_id,
    name,
    salary
FROM {{ ref('stg_employees') }}
