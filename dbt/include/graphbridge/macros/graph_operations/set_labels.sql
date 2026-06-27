{% macro graph_set_labels(old_label, new_label) %}
  MATCH (n:{{ old_label }})
  SET n:{{ new_label }}
  REMOVE n:{{ old_label }}
{% endmacro %}
