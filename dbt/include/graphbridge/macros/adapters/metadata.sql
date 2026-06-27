{% macro graphbridge__record_model_metadata(relation, materialization, identifiers) %}
  {% set cypher %}
    MERGE (m:_dbt_model {name: '{{ relation.identifier }}'})
    SET m.database = '{{ relation.database }}',
        m.schema = '{{ relation.schema }}',
        m.materialization = '{{ materialization }}',
        m.identifiers = {{ identifiers | tojson }},
        m.last_run_at = datetime()
  {% endset %}
  {% do adapter.execute_cypher(cypher) %}
{% endmacro %}
