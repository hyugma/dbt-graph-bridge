# dbt-graph-bridge

**dbt-graph-bridge** is a powerful dbt adapter that bridges traditional Relational Databases (RDBs) with Graph Databases (like Neo4j). 

Unlike a pure graph database adapter, `dbt-graph-bridge` allows you to transform your data using standard SQL in a traditional RDB engine (DuckDB, PostgreSQL, Snowflake, etc.), and seamlessly output the final transformed models directly into a Graph Database as Nodes and Relationships using auto-generated Cypher queries.

## Architecture

This adapter uses a **Dual-Engine Architecture**:
1. **SQL Engine**: Handles standard dbt `table` and `view` materializations, running raw SQL queries and CTEs on RDB backends like `duckdb`.
2. **Graph Engine**: Handles custom `node` and `relationship` materializations, running batch `MERGE` operations on Graph DB backends like `neo4j`.

This enables analysts to model highly complex graph data relationships using the SQL skills they already have, while benefiting from dbt's powerful DAG lineage and testing frameworks.

## Installation

```bash
# Clone the repository
git clone git@github.com:hyugma/dbt-graph-bridge.git
cd dbt-graph-bridge

# Create a virtual environment and install
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Getting Started (Example)

An end-to-end example using the Forbes Global 2000 dataset is available in the `examples/duckdb_to_neo4j` directory.

### 1. Setup the profile
Ensure your `~/.dbt/profiles.yml` (or local `profiles.yml`) contains a target configured for `type: graphbridge`:

```yaml
duckdb_to_neo4j:
  target: neo4j_dev
  outputs:
    neo4j_dev:
      type: graphbridge
      
      # RDB Engine (Source/Transformation)
      sql_engine: duckdb
      sql_engine_config:
        path: 'warehouse.duckdb'

      # Graph Engine (Target)
      graph_engine: neo4j
      graph_host: '127.0.0.1'
      graph_port: 7687
      graph_user: neo4j
      graph_password: 'your_password'
```

### 2. Run the pipeline
```bash
cd examples/duckdb_to_neo4j
dbt run --target neo4j_dev
```

This will:
1. Load CSV seeds into DuckDB.
2. Build clean staging tables using standard SQL.
3. Automatically generate Cypher to create `:Company`, `:Industry`, and `:CEO` nodes in Neo4j.
4. Draw `:LED_BY`, `:HEADQUARTERED_IN`, and `:BELONGS_TO` relationships in Neo4j.

## Supported Engines

**SQL Engines (Sources)**:
- `duckdb`
- `sqlalchemy` (Future support)

**Graph Engines (Targets)**:
- `neo4j`
- `neptune` (Future support)

## License
Apache License 2.0
