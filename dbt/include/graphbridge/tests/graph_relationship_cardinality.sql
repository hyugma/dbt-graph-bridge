{% test graph_relationship_cardinality(model, node_label, relationship_type, direction='outgoing', min=1, max=1) %}

{% set dir_pattern = '-[:' ~ relationship_type ~ ']->' if direction == 'outgoing' else '<-[:' ~ relationship_type ~ ']-' %}

MATCH (n:{{ node_label }})
WITH n, size((n){{ dir_pattern }}()) AS degree
WHERE degree < {{ min }} OR degree > {{ max }}
RETURN n, degree

{% endtest %}
