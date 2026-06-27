{{ config(materialized='table') }}

SELECT
    naturalId AS company_id,
    organizationName AS company_name,
    TRY_CAST(rank AS INTEGER) AS rank,
    TRY_CAST(revenue AS FLOAT) AS revenue,
    TRY_CAST(profits AS FLOAT) AS profits,
    TRY_CAST(assets AS FLOAT) AS assets,
    TRY_CAST(marketValue AS FLOAT) AS marketValue,
    TRY_CAST(employees AS INTEGER) AS employees,
    TRY_CAST(yearFounded AS INTEGER) AS yearFounded,
    description,
    webSite,
    industry,
    country,
    city,
    state,
    ceoName,
    ceoTitle,
    "parentCompany.naturalId" AS parent_company_id,
    "parentCompany.name" AS parent_company_name
FROM read_csv_auto('seeds/Forbes_Global_2000_2026.csv', header=True)
WHERE naturalId IS NOT NULL
