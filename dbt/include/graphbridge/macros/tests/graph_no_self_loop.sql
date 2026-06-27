{% test graph_no_self_loop(model, relationship_type) %}

MATCH (a)-[r:{{ relationship_type }}]->(a)
RETURN r

{% endtest %}
