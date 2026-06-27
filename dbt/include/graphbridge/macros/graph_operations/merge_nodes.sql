{% macro graph_merge_nodes(source_label, target_label, merge_key) %}
  MATCH (n:{{ source_label }})
  WITH n.{{ merge_key }} AS key, collect(n) AS nodes
  CALL apoc.refactor.mergeNodes(nodes) YIELD node
  SET node:{{ target_label }}
  REMOVE node:{{ source_label }}
{% endmacro %}
