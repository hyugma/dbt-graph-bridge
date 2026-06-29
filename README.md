# dbt-graph-bridge

**dbt-graph-bridge** is a powerful dbt adapter that bridges traditional Relational Databases (RDBs) with Graph Databases (like Neo4j). 

Unlike a pure graph database adapter, `dbt-graph-bridge` lets you keep relational transformations in the native dbt adapter for your RDB, then output the final graph-ready models into a Graph Database as Nodes and Relationships using generated Cypher queries.

## Architecture

This adapter follows an **RDB native adapter first** architecture:
1. **RDB phase**: Use the existing dbt adapter for the relational backend, such as `dbt-duckdb`, `dbt-clickhouse`, `dbt-snowflake`, or `dbt-bigquery`, to build seeds, staging, intermediate, and mart models.
2. **Graph phase**: Use `dbt-graph-bridge` for custom `node` and `relationship` materializations, reading graph-ready RDB tables and writing batch graph operations to a Graph DB such as Neo4j.

This keeps RDB-specific DDL, quoting, table engines, incremental behavior, and dialect handling in the mature native dbt adapters. `dbt-graph-bridge` focuses on the bridge from relational result sets to graph structures.

## Validated Adapter Flows

The RDB native adapter first workflow has been validated with:

| RDB adapter | Example | RDB phase | Graph phase |
|---|---|---|---|
| `dbt-duckdb` / `dbt-clickhouse` | `examples/rdb_to_neo4j` | Same seed and staging model built through either native RDB target | Same graph models can read either RDB backend and write to Neo4j/AuraDB |

This example confirms that `dbt-graph-bridge` does not need to reimplement RDB-specific SQL materializations. It can delegate RDB work to the native dbt adapter and use `sql_engine: dbt_adapter` as a read/query backend during graph materialization.

## Installation

```bash
# Clone the repository
git clone git@github.com:hyugma/dbt-graph-bridge.git
cd dbt-graph-bridge

# Create a virtual environment and install
python -m venv .venv
source .venv/bin/activate
pip install -e .

# To run the bundled DuckDB/ClickHouse examples against Neo4j
pip install -e ".[examples]"
pip install graphbridge-neo4j
```

`graphbridge-neo4j` is a separate graph engine add-on package. During local development, install it from its own repository or local checkout before running a `graph_engine: neo4j` target.

## Getting Started (Unified Example)

An end-to-end example using the Forbes company dataset is available in the `examples/rdb_to_neo4j` directory. It demonstrates one dbt project with multiple targets:

- `duckdb_dev`
- `clickhouse_dev`
- `neo4j_from_duckdb`
- `neo4j_from_clickhouse`

### 1. Setup the profile
Ensure your `~/.dbt/profiles.yml` (or local `profiles.yml`) contains a target configured for `type: graphbridge`:

```yaml
rdb_to_neo4j:
  target: duckdb_dev
  outputs:
    duckdb_dev:
      type: duckdb
      <<: &duckdb_connection
        path: warehouse.duckdb

    neo4j_from_duckdb:
      type: graphbridge
      
      # RDB read/query backend. Build RDB tables with --target duckdb_dev first.
      sql_engine: dbt_adapter
      sql_engine_config:
        adapter: duckdb
        profile:
          database: main
          schema: main
          <<: *duckdb_connection

      # Graph Engine (Target)
      graph_engine: neo4j
      graph_host: '127.0.0.1'
      graph_port: 7687
      graph_user: neo4j
      graph_password: 'your_password'
```

The native RDB target and the graphbridge read backend should point at the same RDB relation store. The examples use YAML anchors such as `&duckdb_connection` and `*duckdb_connection` to avoid duplicating those connection values.

### 2. Run the pipeline
Install the example adapters before running this example:

```bash
pip install -e ".[examples]"
```

DuckDB path:

```bash
cd examples/rdb_to_neo4j
dbt seed --profiles-dir . --target duckdb_dev --full-refresh
dbt run --profiles-dir . --target duckdb_dev
dbt run --profiles-dir . --target neo4j_from_duckdb
```

ClickHouse path:

```bash
cd examples/rdb_to_neo4j
dbt seed --profiles-dir . --target clickhouse_dev --full-refresh
dbt run --profiles-dir . --target clickhouse_dev
dbt run --profiles-dir . --target neo4j_from_clickhouse
```

This will:
1. Load CSV seeds into DuckDB or ClickHouse with the native dbt adapter.
2. Build clean staging tables with the native dbt adapter.
3. Read graph-ready RDB tables through the `dbt_adapter` read backend.
4. Generate Cypher to create `:Company`, `:Industry`, and `:CEO` nodes in Neo4j.
5. Draw `:LED_BY`, `:HEADQUARTERED_IN`, and `:BELONGS_TO` relationships in Neo4j.

The example disables RDB table models when `target.type == 'graphbridge'`, so a bare graphbridge run runs only graph models. Run the matching native RDB target first so the graph-ready tables already exist.

## Supported Engines

**SQL Engines (Sources)**:
- `duckdb`
- `sqlalchemy`
- `dbt_adapter` read/query backend for installed dbt adapters

Validated native dbt adapter backends:
- `dbt-duckdb`
- `dbt-clickhouse`

**Graph Engines (Targets)**:
- Install a graph engine add-on separately, such as `graphbridge-neo4j`, `graphbridge-neptune`, or `graphbridge-memgraph`
- `graphbridge-neo4j` is registered as `graph_engine: neo4j`

Graph engine add-ons expose a callable client class or factory that implements the `GraphEngineClient` contract:

```toml
[project.entry-points."dbt_graph_bridge.graph_engine"]
graphbridge-neo4j = "graphbridge_neo4j:Neo4jClient"
graphbridge-neptune = "graphbridge_neptune:NeptuneClient"
graphbridge-memgraph = "graphbridge_memgraph:MemgraphClient"
```

Then select it in a graphbridge target:

```yaml
graph_engine: neptune
```

This keeps RDB support delegated to native dbt adapters while graph database support can grow through focused graph-side add-ons.

## License
Apache License 2.0
