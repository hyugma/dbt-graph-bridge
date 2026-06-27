{% test graph_no_self_loop(model, relationship_type) %}

MATCH (n)-[r:{{ relationship_type }}]->(n)
RETURN n, count(r) AS self_loop_count

{% endtest %}
