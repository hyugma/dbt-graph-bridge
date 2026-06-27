{% materialization node, adapter='graphbridge' %}

  {%- set labels = config.get('labels', [this.name]) -%}
  {%- set unique_key = config.get('unique_key') -%}
  {%- set strategy = config.get('strategy', 'merge') -%}
  {%- set indexes = config.get('indexes', []) -%}
  {%- set constraints = config.get('constraints', []) -%}

  {% if not unique_key %}
    {{ exceptions.raise_compiler_error("The 'unique_key' configuration is required for 'node' materialization.") }}
  {% endif %}

  -- 1. Constraint Creation (Idempotent)
  {% for constraint in constraints %}
    {% do adapter.create_constraints(this, [constraint]) %}
  {% endfor %}

  -- 2. Index Creation (Idempotent)
  {% for index in indexes %}
    {% do adapter.create_indexes(this, [index]) %}
  {% endfor %}

  -- 3. Data Retrieval (Run SQL to get Python dicts via dbt-duckdb or similar source)
  {%- set source_data = run_query(sql) -%}

  -- 4. Replace Strategy: Drop existing nodes
  {% if strategy == 'replace' %}
    {% do adapter.drop_relation(this) %}
  {% endif %}

  -- 5. Cypher Generation & Batch Execution
  {%- set columns = source_data.column_names -%}
  {%- set merge_cypher = adapter.dispatch('generate_node_merge', 'graphbridge')(labels, unique_key, columns) -%}

  {%- set batch_size = config.get('batch_size', var('graph_batch_size', 10000)) -%}
  {% set batch_data = [] %}
  {% for row in source_data %}
    {% do batch_data.append(row.dict()) %}
  {% endfor %}
  {% do adapter.execute_cypher_batch(merge_cypher, batch_data, batch_size) %}

  -- 6. Record Metadata
  {{ adapter.dispatch('record_model_metadata', 'graphbridge')(this, 'node', labels) }}

  -- 7. Satisfy dbt-core's expectation for a 'main' statement
  {% set total_records = batch_data | length %}
  {% call statement('main') %}
    /* graphbridge_rows_affected: {{ total_records }} */
    RETURN 'OK' AS result
  {% endcall %}

  {{ return({'relations': [this]}) }}

{% endmaterialization %}



