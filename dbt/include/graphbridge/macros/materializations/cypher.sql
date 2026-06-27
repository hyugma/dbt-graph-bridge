{% materialization cypher, adapter='graphbridge' %}

  -- 1. pre_hooks
  {% for hook in config.get('pre_hooks', []) %}
    {% do adapter.execute_cypher(hook) %}
  {% endfor %}

  -- 2. Cypher Execution
  {% do adapter.execute_cypher(sql) %}

  -- 3. post_hooks
  {% for hook in config.get('post_hooks', []) %}
    {% do adapter.execute_cypher(hook) %}
  {% endfor %}

  -- 4. Record Metadata
  {{ adapter.dispatch('record_model_metadata', 'graphbridge')(this, 'cypher', []) }}

  {{ return({'relations': [this]}) }}

{% endmaterialization %}
