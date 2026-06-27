{% macro graph_delete_orphans(label, relationship_type=None) %}
  {% if relationship_type %}
    MATCH (n:{{ label }})
    WHERE NOT EXISTS { (n)-[:{{ relationship_type }}]-() }
    DETACH DELETE n
  {% else %}
    MATCH (n:{{ label }})
    WHERE NOT EXISTS { (n)--() }
    DETACH DELETE n
  {% endif %}
{% endmacro %}
