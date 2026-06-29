{{ config(materialized='table') }}

SELECT
    {{ empty_to_null('company_name') }} AS company_id,
    {{ empty_to_null('company_name') }} AS company_name,
    {{ safe_int(adapter.quote('rank')) }} AS rank,
    {{ empty_to_null('description') }} AS description,
    {{ empty_to_null('state') }} AS state,
    {{ empty_to_null('industry') }} AS industry,
    {{ empty_to_null('country') }} AS country,
    {{ safe_float('revenue') }} AS revenue,
    {{ safe_float('profits') }} AS profits,
    {{ safe_float('assets') }} AS assets,
    {{ safe_float('market_value') }} AS market_value,
    {{ safe_int('profits_rank') }} AS profits_rank,
    {{ safe_int('assets_rank') }} AS assets_rank,
    {{ safe_int('market_value_rank') }} AS market_value_rank,
    {{ safe_int('employees') }} AS employees,
    {{ safe_int('revenue_rank') }} AS revenue_rank,
    {{ empty_to_null('ceo_name') }} AS ceo_name,
    {{ empty_to_null('ceo_title') }} AS ceo_title,
    {{ empty_to_null('city') }} AS city,
    {{ safe_int('year_founded') }} AS year_founded,
    {{ empty_to_null('web_site') }} AS web_site
FROM {{ ref('companies') }}
WHERE {{ empty_to_null('company_name') }} IS NOT NULL
