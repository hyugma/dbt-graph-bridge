{% macro safe_int(expression) -%}
  {{ return(adapter.dispatch('safe_int', 'rdb_to_neo4j')(expression)) }}
{%- endmacro %}

{% macro default__safe_int(expression) -%}
  TRY_CAST({{ expression }} AS INTEGER)
{%- endmacro %}

{% macro clickhouse__safe_int(expression) -%}
  toInt64OrNull(toString({{ expression }}))
{%- endmacro %}

{% macro safe_float(expression) -%}
  {{ return(adapter.dispatch('safe_float', 'rdb_to_neo4j')(expression)) }}
{%- endmacro %}

{% macro default__safe_float(expression) -%}
  TRY_CAST({{ expression }} AS FLOAT)
{%- endmacro %}

{% macro clickhouse__safe_float(expression) -%}
  toFloat64OrNull(toString({{ expression }}))
{%- endmacro %}

{% macro empty_to_null(expression) -%}
  {{ return(adapter.dispatch('empty_to_null', 'rdb_to_neo4j')(expression)) }}
{%- endmacro %}

{% macro default__empty_to_null(expression) -%}
  NULLIF({{ expression }}, '')
{%- endmacro %}

{% macro clickhouse__empty_to_null(expression) -%}
  nullIf(toString({{ expression }}), '')
{%- endmacro %}
