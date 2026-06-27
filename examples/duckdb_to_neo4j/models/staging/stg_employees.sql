{{ config(materialized='table') }}

SELECT
    emp_id::VARCHAR AS employee_id,
    name,
    department,
    salary::INTEGER AS salary
FROM read_csv_auto('seeds/employees.csv')
