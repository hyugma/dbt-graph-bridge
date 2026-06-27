{% macro graphbridge__generate_node_merge(labels, unique_key, columns) %}
  {% set label_str = labels | join(':') %}
  {% set set_clauses = [] %}
  {% for col in columns %}
    {% if col != unique_key %}
      {% do set_clauses.append("n." ~ col ~ " = row." ~ col) %}
    {% endif %}
  {% endfor %}

  {% set cypher %}
    UNWIND $batch AS row
    MERGE (n:{{ label_str }} { {{ unique_key }}: row.{{ unique_key }} })
    {% if set_clauses %}
    SET {{ set_clauses | join(', ') }},
        n._dbt_loaded_at = datetime()
    {% else %}
    SET n._dbt_loaded_at = datetime()
    {% endif %}
  {% endset %}

  {{ return(cypher) }}
{% endmacro %}

{% macro graphbridge__generate_relationship_merge(relationship_type, source_node, target_node, columns) %}
  {% set src_label = source_node.get('labels', []) | join(':') %}
  {% set src_key = source_node.get('key') %}
  {% set src_col = source_node.get('column') %}

  {% set tgt_label = target_node.get('labels', []) | join(':') %}
  {% set tgt_key = target_node.get('key') %}
  {% set tgt_col = target_node.get('column') %}

  {% set set_clauses = [] %}
  {% for col in columns %}
    {% if col != src_col and col != tgt_col %}
      {% do set_clauses.append("r." ~ col ~ " = row." ~ col) %}
    {% endif %}
  {% endfor %}

  {% set cypher %}
    UNWIND $batch AS row
    MATCH (src:{{ src_label }} { {{ src_key }}: row.{{ src_col }} })
    MATCH (tgt:{{ tgt_label }} { {{ tgt_key }}: row.{{ tgt_col }} })
    MERGE (src)-[r:{{ relationship_type }}]->(tgt)
    {% if set_clauses %}
    SET {{ set_clauses | join(', ') }},
        r._dbt_loaded_at = datetime()
    {% else %}
    SET r._dbt_loaded_at = datetime()
    {% endif %}
  {% endset %}

  {{ return(cypher) }}
{% endmacro %}
