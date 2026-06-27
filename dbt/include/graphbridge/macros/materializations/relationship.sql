{% materialization relationship, adapter='graphbridge' %}

  {%- set relationship_type = config.get('relationship_type', this.name | upper) -%}
  {%- set source_node = config.get('source_node') -%}
  {%- set target_node = config.get('target_node') -%}
  {%- set strategy = config.get('strategy', 'merge') -%}

  {% if not source_node or not target_node %}
    {{ exceptions.raise_compiler_error("Both 'source_node' and 'target_node' configurations are required for 'relationship' materialization.") }}
  {% endif %}

  -- 1. Data Retrieval
  {%- set source_data = run_query(sql) -%}
  {%- set columns = source_data.column_names -%}

  -- 2. Replace Strategy: Drop existing relationships
  {% if strategy == 'replace' %}
    {% do adapter.drop_relation(this) %}
  {% endif %}

  -- 3. Cypher Generation & Batch Execution
  {%- set merge_cypher = adapter.dispatch('generate_relationship_merge', 'graphbridge')(relationship_type, source_node, target_node, columns) -%}

  {%- set batch_size = config.get('batch_size', var('graph_batch_size', 10000)) -%}
  {% set batch_data = [] %}
  {% for row in source_data %}
    {% do batch_data.append(row.dict()) %}
  {% endfor %}
  {% do adapter.execute_cypher_batch(merge_cypher, batch_data, batch_size) %}

  -- 4. Record Metadata
  {{ adapter.dispatch('record_model_metadata', 'graphbridge')(this, 'relationship', [relationship_type]) }}

  -- 5. Satisfy dbt-core's expectation for a 'main' statement
  {% call statement('main') %}
    RETURN 'OK' AS result
  {% endcall %}

  {{ return({'relations': [this]}) }}

{% endmaterialization %}



