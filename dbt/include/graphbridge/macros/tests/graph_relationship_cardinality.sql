{% test graph_relationship_cardinality(model, relationship_type, from_label, to_label, max_outgoing=1) %}

MATCH (a:{{ from_label }})-[r:{{ relationship_type }}]->(b:{{ to_label }})
WITH a, count(r) as out_degree
WHERE out_degree > {{ max_outgoing }}
RETURN a

{% endtest %}
