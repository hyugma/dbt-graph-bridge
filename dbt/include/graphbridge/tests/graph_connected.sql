{% test graph_connected(model, node_label, relationship_type, direction='outgoing', min_degree=1) %}

{% set dir_pattern = '-[r:' ~ relationship_type ~ ']->' if direction == 'outgoing' else '<-[r:' ~ relationship_type ~ ']-' %}

MATCH (n:{{ node_label }})
WHERE NOT EXISTS { (n){{ dir_pattern }}() }
RETURN n, count(*) AS orphan_count

{% endtest %}
