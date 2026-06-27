{% materialization cypher_incremental, adapter='graphbridge' %}
  -- Not implemented in v0.1.0
  {{ exceptions.raise_compiler_error("The 'cypher_incremental' materialization is not yet implemented.") }}
{% endmaterialization %}
