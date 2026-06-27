{% materialization graph, adapter='graphbridge' %}
  -- Not implemented in v0.1.0
  {{ exceptions.raise_compiler_error("The 'graph' materialization is not yet implemented.") }}
{% endmaterialization %}
