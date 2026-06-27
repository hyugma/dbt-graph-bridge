{% materialization graph_snapshot, adapter='graphbridge' %}

  {%- set unique_key = config.get('unique_key') -%}
  {%- set strategy = config.get('strategy', 'timestamp') -%}
  {%- set updated_at = config.get('updated_at') -%}
  {%- set snapshot_label = config.get('snapshot_label') -%}
  {%- set snapshot_relationship = config.get('snapshot_relationship', 'HAS_SNAPSHOT') -%}

  -- Not fully implemented in v0.1.0
  {{ exceptions.raise_compiler_error("The 'graph_snapshot' materialization is not yet fully implemented.") }}

  {{ return({'relations': [this]}) }}

{% endmaterialization %}
