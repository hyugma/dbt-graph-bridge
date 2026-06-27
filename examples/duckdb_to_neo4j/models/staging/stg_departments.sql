{{ config(materialized='table') }}

SELECT
    dept_id::INTEGER AS department_id,
    name AS department_name,
    location
FROM read_csv_auto('seeds/departments.csv')
