# dbt-graph-bridge Specification

> Status: implementation-aligned draft
> Repository version: 0.1.0
> Package name: `dbt-graph-bridge`
> Adapter type: `graphbridge`

## 1. Overview

`dbt-graph-bridge` is a dbt adapter that bridges a relational SQL engine and a graph database.

The current implementation is designed around an RDB native adapter first pipeline:

1. The native dbt adapter for the RDB executes seeds, staging, intermediate, marts, table/view materializations, DDL, and dialect-specific behavior.
2. `dbt-graph-bridge` reads graph-ready tabular result sets from the RDB and writes them as graph nodes, relationships, or direct Cypher operations.

The adapter is not a pure graph-only dbt adapter. It also should not become a replacement implementation for existing RDB dbt adapters. RDB-specific materialization behavior belongs to mature native adapters such as `dbt-duckdb`, `dbt-clickhouse`, `dbt-snowflake`, `dbt-bigquery`, `dbt-databricks`, or similar packages.

## 2. Design Principle: RDB Native Adapter First

The central design rule is:

> RDB-side physical modeling is owned by the native dbt adapter. `dbt-graph-bridge` owns only the bridge from graph-ready relational data to graph database writes.

This means:

- Use the native RDB target to build relational resources:
  - seeds
  - staging models
  - intermediate models
  - marts
  - table/view/incremental materializations
  - RDB-specific DDL
- Use the graphbridge target only for graph resources:
  - `node`
  - `relationship`
  - `cypher`
  - future graph-specific materializations
- The `dbt_adapter` SQL engine is a read/query backend for graphbridge. It is not intended to run RDB DDL inside graphbridge.
- Existing dbt adapters should be reused for RDB behavior wherever possible. Graph database integrations should be implemented through graph engine clients or add-ons.

Typical execution:

```bash
# Phase 1: build relational data with the native RDB adapter
dbt run --target clickhouse_dev --select staging intermediate marts

# Phase 2: write graph data with graphbridge
dbt run --target neo4j_from_clickhouse
```

## 3. Current Repository Layout

```text
dbt-graph-bridge/
├── dbt/adapters/graphbridge/
│   ├── __init__.py
│   ├── __version__.py
│   ├── column.py
│   ├── connections.py
│   ├── graph_engines.py
│   ├── impl.py
│   ├── relation.py
│   ├── sql_engines.py
│   └── type_mapping.py
├── dbt/include/graphbridge/
│   ├── dbt_project.yml
│   └── macros/
│       ├── adapters/
│       ├── graph_operations/
│       ├── materializations/
│       └── tests/
├── examples/rdb_to_neo4j/
├── README.md
├── pyproject.toml
├── uv.lock
└── CHANGELOG.md
```

## 4. Package Metadata

The package is defined in `pyproject.toml`.

- Project name: `dbt-graph-bridge`
- Version: `0.1.0`
- Python requirement: `>=3.10`
- dbt entry point: `graphbridge = "dbt.adapters.graphbridge"`
- Runtime dependencies:
  - `dbt-adapters>=1.0.0,<2.0.0`
  - `dbt-common>=1.0.0,<2.0.0`
  - `duckdb>=1.0.0,<2.0.0`
  - `neo4j>=5.0.0,<6.0.0`
  - `pyarrow>=12.0.0`
- Development dependencies:
  - `pytest`
  - `dbt-tests-adapter`
  - `black`
  - `ruff`
  - `mypy`

## 5. Supported Engines

### 5.1 SQL engines

Implemented:

- `duckdb`
- `sqlalchemy`
- `dbt_adapter`

The default SQL engine is DuckDB for local/simple projects. DuckDB is used through an embedded connection created by `duckdb.connect(database=path, read_only=False)`.

The SQLAlchemy engine expects `sql_engine_config.connection_url`.

The `dbt_adapter` engine loads an installed dbt adapter, constructs its credentials from `sql_engine_config.profile`, and uses it as a read/query backend. It is intended for graph materializations that select from RDB tables already created by the native target. It should not be used for RDB table/view materialization inside graphbridge.

### 5.2 Validated native dbt adapters

The `dbt_adapter` SQL engine has been validated as a read/query backend with the following native dbt adapters:

| Native adapter | Example project | RDB phase result | Graph phase result |
|---|---|---|---|
| `dbt-duckdb` and `dbt-clickhouse` | `examples/rdb_to_neo4j` | Same seed and staging model can be built through either native RDB target | Same graph model set can read either RDB backend and write to Neo4j/AuraDB |

This validates the core architectural boundary:

- RDB DDL and physical table creation stay in the native dbt adapter.
- graphbridge reads completed RDB relations via `dbt_adapter`.
- graphbridge writes only graph resources to Neo4j/AuraDB.

### 5.3 Graph engines

Implemented:

- `neo4j`

The Neo4j backend uses the official Neo4j Python driver.

Future graph engines are not implemented in this repository.

## 6. Profile Configuration

A `graphbridge` target configures both sides of the bridge.

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

      sql_engine: dbt_adapter
      sql_engine_config:
        adapter: duckdb
        profile:
          database: main
          schema: main
          <<: *duckdb_connection

      graph_engine: neo4j
      graph_scheme: neo4j
      graph_host: 127.0.0.1
      graph_port: 7687
      graph_database: neo4j
      graph_user: neo4j
      graph_password: changeme
      graph_encrypted: false

      connection_timeout: 30
      max_connection_lifetime: 3600
      max_connection_pool_size: 100
      connection_acquisition_timeout: 60
```

The RDB connection values should be shared between the native RDB target and the graphbridge read backend. The example above uses a YAML anchor to avoid duplicated connection values. The native target still needs its own `type`, while `sql_engine_config.profile` receives only the credential fields expected by the native adapter.

### 6.1 Credential fields

The adapter credentials are defined by `GraphBridgeCredentials`.

| Field | Default | Description |
|---|---:|---|
| `sql_engine` | `duckdb` | SQL backend name. |
| `sql_engine_config` | `{path: warehouse.duckdb}` | SQL backend-specific settings. |
| `graph_engine` | `neo4j` | Graph backend name. |
| `graph_scheme` | `neo4j` | URI scheme used for Neo4j. |
| `graph_host` | `localhost` | Graph database host. |
| `graph_port` | `7687` | Graph database port. |
| `graph_database` | `neo4j` | Neo4j database name. |
| `graph_user` | `neo4j` | Neo4j user. |
| `graph_password` | empty string | Neo4j password. |
| `graph_encrypted` | `false` | Neo4j encrypted driver setting. |
| `connection_timeout` | `30` | Driver connection timeout. |
| `max_connection_lifetime` | `3600` | Driver connection lifetime. |
| `max_connection_pool_size` | `100` | Driver pool size. |
| `connection_acquisition_timeout` | `60` | Driver acquisition timeout. |
| `database` | `neo4j` | dbt database field. |
| `schema` | `public` | dbt schema field. |

The Neo4j URI is constructed as:

```text
{graph_scheme}://{graph_host}:{graph_port}
```

### 6.2 Native RDB plus graphbridge profile pattern

Projects using warehouse adapters such as ClickHouse, Snowflake, BigQuery, Databricks, or Redshift should define both a native RDB target and a graphbridge target.

```yaml
rdb_to_neo4j:
  target: clickhouse_dev
  outputs:
    clickhouse_dev:
      type: clickhouse
      <<: &clickhouse_connection
        schema: default
        host: example.clickhouse.cloud
        port: 8443
        user: default
        password: "{{ env_var('CLICKHOUSE_PASSWORD') }}"
        secure: true
        driver: http

    neo4j_from_clickhouse:
      type: graphbridge

      sql_engine: dbt_adapter
      sql_engine_config:
        adapter: clickhouse
        profile:
          <<: *clickhouse_connection

      graph_engine: neo4j
      graph_scheme: neo4j+s
      graph_host: "{{ env_var('NEO4J_HOST') }}"
      graph_database: "{{ env_var('NEO4J_DATABASE') }}"
      graph_user: "{{ env_var('NEO4J_USER') }}"
      graph_password: "{{ env_var('NEO4J_PASSWORD') }}"
```

In this pattern, run RDB models with `clickhouse_dev` and graph models with `neo4j_from_clickhouse`. The unified example also provides a `duckdb_dev` / `neo4j_from_duckdb` pair using the same model tree.

## 7. Connection Lifecycle

`GraphBridgeConnectionManager.open()` creates both backend clients and stores them in `connection.handle`.

```python
{
    "graph_client": GraphEngineClient,
    "sql_client": SQLEngineClient,
}
```

When opening a connection, the graph client verifies connectivity first. If Neo4j is unavailable or credentials are invalid, the dbt connection fails.

Transaction methods are currently no-ops:

- `begin()`
- `commit()`
- `cancel()`
- `cancel_open()`

## 8. Query Routing

The adapter routes statements in `GraphBridgeConnectionManager.execute()`.

### 8.1 SQL routing

Statements that look like SQL are routed to the configured SQL engine.

SQL detection currently recognizes statements beginning with:

- `SELECT`
- `WITH`
- `CREATE TABLE`
- `CREATE VIEW`
- `DROP`
- `ALTER`
- `INSERT`
- `BEGIN`
- `COMMIT`

Before detection, SQL-style and Cypher-style comments are stripped.

When SQL is sent to DuckDB, the adapter also:

- Removes dbt-injected `"database"."schema".` prefixes.
- Rewrites `CREATE TABLE` to `CREATE OR REPLACE TABLE` for idempotent model builds.
- Replaces dbt-style `%s` parameters with DuckDB-style `?` parameters.

When `sql_engine: dbt_adapter` is used, graphbridge allows read SQL only, currently statements beginning with `SELECT` or `WITH`. Any DDL/DML statement such as `CREATE TABLE`, `DROP`, `ALTER`, or `INSERT` raises a runtime error. This protects the RDB native adapter first boundary and avoids reimplementing RDB materializations inside graphbridge.

If SQL execution fails after a statement has been classified as SQL, the adapter raises a dbt runtime error. It does not fall through to the graph engine.

### 8.2 Cypher routing

Statements that do not match SQL detection are routed to Neo4j as Cypher.

Cypher execution returns an `AdapterResponse` with rows affected computed from Neo4j summary counters:

- nodes created/deleted
- relationships created/deleted
- properties set

### 8.3 dbt generic test interception

dbt generic tests wrap test SQL in a `select count(*) ... from (...) dbt_internal_test` statement.

The adapter detects wrapped Cypher test bodies that start with `MATCH`, executes the Cypher directly, and converts the number of returned records into dbt's expected `failures`, `should_warn`, and `should_error` table.

### 8.4 Rows affected marker

Graph materializations add a comment marker:

```sql
/* graphbridge_rows_affected: 123 */
RETURN 'OK' AS result
```

The adapter detects this marker for Cypher statements and returns the marked row count as `rows_affected`.

## 9. Relations and Catalog Behavior

`GraphBridgeRelation` extends dbt's `BaseRelation`.

Implemented relation types:

- `node_label`
- `relationship_type`
- `cypher_view`
- `graph`
- `table`
- `view`
- `cte`
- `external`

`create_from()` maps model materializations as follows:

| Materialization | Relation type |
|---|---|
| `node` | `node_label` |
| `node_incremental` | `node_label` |
| `relationship` | `relationship_type` |
| `relationship_incremental` | `relationship_type` |
| other | `graph` |

`list_relations_without_caching()` queries Neo4j labels and relationship types:

- `CALL db.labels() YIELD label RETURN label`
- `CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType`

Labels starting with `_dbt_` and relationship types starting with `_DBT_` are skipped.

`get_catalog()` currently returns an empty catalog.

## 10. Materializations

### 10.1 `node`

The `node` materialization converts the result of a SQL model into Neo4j nodes.

Required config:

- `unique_key`

Optional config:

- `labels`, default: `[this.name]`
- `strategy`, default: `merge`
- `indexes`, default: `[]`
- `constraints`, default: `[]`
- `batch_size`, default: `var('graph_batch_size', 10000)`

Example:

```sql
{{ config(
    materialized='node',
    labels=['Company'],
    unique_key='company_id',
    indexes=[
        {'properties': ['company_name']},
        {'properties': ['rank']}
    ]
) }}

select
    company_id,
    company_name,
    rank,
    revenue
from stg_forbes_g2k
where company_id is not null
```

Execution steps:

1. Validate that `unique_key` is present.
2. Create configured constraints through `adapter.create_constraints()`.
3. Create configured indexes through `adapter.create_indexes()`.
4. Execute the model SQL through `run_query(sql)`.
5. If `strategy == 'replace'`, drop existing nodes for the relation.
6. Generate a Cypher `UNWIND $batch` / `MERGE` query.
7. Execute rows with `adapter.execute_cypher_batch()`.
8. Record metadata in Neo4j using `_dbt_model` nodes.
9. Emit a final dbt-compatible main statement with `graphbridge_rows_affected`.

Generated node merge shape:

```cypher
UNWIND $batch AS row
MERGE (n:Label { unique_key: row.unique_key })
SET n.property = row.property,
    n._dbt_loaded_at = datetime()
```

Current behavior:

- All columns except `unique_key` become properties.
- The merge key remains the node identity key.
- No column-level type casting is performed by the Jinja macro.
- Python batch sanitization converts `Decimal` to `float` and Python date/datetime values to strings before sending to Neo4j.

### 10.2 `relationship`

The `relationship` materialization converts SQL result rows into Neo4j relationships.

Required config:

- `source_node`
- `target_node`

Optional config:

- `relationship_type`, default: `this.name | upper`
- `strategy`, default: `merge`
- `batch_size`, default: `var('graph_batch_size', 10000)`

Example:

```sql
{{ config(
    materialized='relationship',
    relationship_type='HEADQUARTERED_IN',
    source_node={
        'labels': ['Company'],
        'key': 'company_id',
        'column': 'company_id'
    },
    target_node={
        'labels': ['City'],
        'key': 'city',
        'column': 'city'
    }
) }}

select
    company_id,
    city
from stg_forbes_g2k
where company_id is not null
  and city is not null
```

Execution steps:

1. Validate that `source_node` and `target_node` are present.
2. Execute the model SQL through `run_query(sql)`.
3. If `strategy == 'replace'`, drop existing relationships for the relation.
4. Generate a Cypher `UNWIND $batch` / `MATCH` / `MERGE` query.
5. Execute rows with `adapter.execute_cypher_batch()`.
6. Record metadata in Neo4j using `_dbt_model` nodes.
7. Emit a final dbt-compatible main statement with `graphbridge_rows_affected`.

Generated relationship merge shape:

```cypher
UNWIND $batch AS row
MATCH (src:SourceLabel { source_key: row.source_column })
MATCH (tgt:TargetLabel { target_key: row.target_column })
MERGE (src)-[r:RELATIONSHIP_TYPE]->(tgt)
SET r.property = row.property,
    r._dbt_loaded_at = datetime()
```

Current behavior:

- Columns used to match source and target nodes are excluded from relationship properties.
- All other columns become relationship properties.
- The relationship `MERGE` pattern does not include relationship properties in the identity pattern.

### 10.3 `cypher`

The `cypher` materialization executes model contents directly as Cypher.

Supported config:

- `pre_hooks`, default: `[]`
- `post_hooks`, default: `[]`

Execution steps:

1. Execute configured `pre_hooks` as Cypher.
2. Execute the model SQL body as Cypher.
3. Execute configured `post_hooks` as Cypher.
4. Record metadata in Neo4j using `_dbt_model` nodes.

### 10.4 Stubbed or incomplete materializations

The following materializations exist as files but intentionally raise compiler errors in v0.1.0:

- `graph`
- `cypher_incremental`
- `graph_snapshot`

## 11. Indexes and Constraints

Index and constraint creation is implemented in Python adapter methods, not in the placeholder Jinja macros.

### 11.1 Indexes

`adapter.create_indexes(relation, indexes)` supports:

- range indexes
- text indexes
- vector indexes

Range index example:

```yaml
indexes:
  - properties: ['company_name']
```

Text index example:

```yaml
indexes:
  - type: text
    properties: ['description']
```

Vector index example:

```yaml
indexes:
  - type: vector
    properties: ['embedding']
    dimensions: 1536
    similarity_function: cosine
```

### 11.2 Constraints

`adapter.create_constraints(relation, constraints)` supports:

- `unique`
- `not_null`
- `property_type`

Unique constraint example:

```yaml
constraints:
  - type: unique
    properties: ['company_id']
```

Not-null constraint example:

```yaml
constraints:
  - type: not_null
    properties: ['company_name']
```

Property type constraint example:

```yaml
constraints:
  - type: property_type
    property: rank
    property_type: INTEGER
```

## 12. Graph Metadata

Every successful `node`, `relationship`, or `cypher` materialization records metadata in Neo4j.

Metadata is stored as `_dbt_model` nodes:

```cypher
MERGE (m:_dbt_model {name: '<model_identifier>'})
SET m.database = '<database>',
    m.schema = '<schema>',
    m.materialization = '<materialization>',
    m.identifiers = [...],
    m.last_run_at = datetime()
```

## 13. Graph Tests

The repository includes graph-oriented generic tests.

### 13.1 `graph_no_self_loop`

Returns relationships where a relationship points from a node back to itself.

```cypher
MATCH (a)-[r:RELATIONSHIP_TYPE]->(a)
RETURN r
```

### 13.2 `graph_connected`

Returns nodes that do not have the requested relationship direction.

Parameters:

- `node_label`
- `relationship_type`
- `direction`, default: `outgoing`
- `min_degree`, default: `1`

Note: `min_degree` is present in the signature but is not used by the current macro body.

### 13.3 `graph_relationship_cardinality`

Returns source nodes whose outgoing relationship count exceeds `max_outgoing`.

Parameters:

- `relationship_type`
- `from_label`
- `to_label`
- `max_outgoing`, default: `1`

## 14. Graph Operation Macros

The repository includes helper macros for direct graph operations.

### 14.1 `graph_merge_nodes(source_label, target_label, merge_key)`

Uses APOC:

```cypher
MATCH (n:source_label)
WITH n.merge_key AS key, collect(n) AS nodes
CALL apoc.refactor.mergeNodes(nodes) YIELD node
SET node:target_label
REMOVE node:source_label
```

APOC must be available in Neo4j for this macro to work.

### 14.2 `graph_set_labels(old_label, new_label)`

Moves all nodes from one label to another.

### 14.3 `graph_delete_orphans(label, relationship_type=None)`

Deletes nodes with no relationships, or no relationships of a specified type.

## 15. Type Handling

`GraphBridgeColumn` defines SQL-to-graph type mapping.

Examples:

| SQL type | Graph type |
|---|---|
| `BOOLEAN` | `BOOLEAN` |
| `INT`, `INTEGER`, `BIGINT` | `INTEGER` |
| `FLOAT`, `DOUBLE`, `REAL` | `FLOAT` |
| `VARCHAR`, `TEXT` | `STRING` |
| `DATE` | `DATE` |
| `TIMESTAMP` | `LOCAL DATETIME` |
| `TIMESTAMPTZ` | `ZONED DATETIME` |
| `TIME` | `LOCAL TIME` |
| `INTERVAL` | `DURATION` |
| `JSON`, `JSONB` | `MAP` |
| `FLOAT[]` | `LIST<FLOAT>` |

`type_mapping.py` also includes helpers for converting Python values to Neo4j-compatible values. The currently used batch path in `graph_engines.py` performs its own lightweight sanitization for `Decimal`, `date`, and `datetime`.

## 16. Example Project

The supported example project is located at `examples/rdb_to_neo4j`.

It demonstrates the RDB native adapter first pattern with one dbt project and four targets:

- `duckdb_dev`
- `clickhouse_dev`
- `neo4j_from_duckdb`
- `neo4j_from_clickhouse`

The same seed, staging model, graph node models, and graph relationship models can be used for either DuckDB or ClickHouse on the relational side. The graphbridge targets then read the completed `stg_companies` relation from the selected RDB and write graph resources to Neo4j/AuraDB.

The example contains:

- `profiles.yml`
- `dbt_project.yml`
- a Forbes company seed with `snake_case` headers
- compatibility macros for DuckDB and ClickHouse casts/null handling
- one shared staging model
- graph node models
- graph relationship models

Required adapter packages:

```bash
pip install -e ".[examples]"
```

DuckDB path:

```bash
cd examples/rdb_to_neo4j
dbt build --profiles-dir . --target duckdb_dev --full-refresh
dbt run --profiles-dir . --target neo4j_from_duckdb
```

ClickHouse path:

```bash
cd examples/rdb_to_neo4j
dbt build --profiles-dir . --target clickhouse_dev --full-refresh
dbt run --profiles-dir . --target neo4j_from_clickhouse
```

When a graphbridge target is used, staging models are disabled by default and graphbridge runs only graph models. Run the matching native RDB target first so `stg_companies` already exists.

Expected graph output:

- Node models: `CEO:Person`, `City`, `Company`, `Country`, `Industry`
- Relationship models: `BELONGS_TO`, `HEADQUARTERED_IN`, `LED_BY`, `LOCATED_IN`

For dbt docs lineage inspection, the example supports a docs-only var:

```bash
dbt docs generate --profiles-dir . --target neo4j_from_duckdb --vars '{docs_lineage: true}'
```

This includes `stg_companies` in the graphbridge manifest and adds docs-only dependencies from graph node models back to the staging table. It is intended for docs generation and should not be used with `dbt run`.

## 17. CI and Test Status

The GitHub Actions workflow installs the package with development dependencies and runs:

```bash
pytest tests/unit/
```

At the time this specification was written, the repository does not contain a `tests/` directory. The CI configuration and repository contents should be reconciled before relying on CI as a signal.

## 18. Known Limitations

Current v0.1.0 limitations:

- Neo4j connectivity is required when opening a `graphbridge` connection.
- `graph`, `cypher_incremental`, and `graph_snapshot` materializations are not implemented.
- SQL/Cypher routing is heuristic and based on statement prefixes.
- SQL/Cypher routing is heuristic; once a statement is classified as SQL, SQL engine failures are surfaced directly.
- `dbt_adapter` is intentionally read-only inside graphbridge. RDB DDL must be executed with the native adapter target.
- `get_catalog()` returns an empty catalog.
- `begin()`, `commit()`, and cancellation methods are no-ops.
- Relationship identity is based only on source node, target node, and relationship type.
- Jinja-generated Cypher does not quote labels, relationship types, or property names.
- Column-level Cypher casts are not currently applied in node or relationship merge macros.
- `graph_connected` accepts `min_degree` but does not apply it.
- The SQLAlchemy backend is implemented but not covered by examples in this repository.

## 19. Implementation Targets for Future Work

Likely next steps:

1. Add unit tests for query routing, Cypher generation, credentials, and materialization behavior.
2. Align CI with the actual test directory.
3. Add an integration test harness for DuckDB plus Neo4j.
4. Add tests that assert SQL engine failures do not fall through to Cypher execution.
5. Add tests that assert `dbt_adapter` rejects DDL inside graphbridge.
6. Implement or remove stub materializations.
7. Add identifier escaping for generated Cypher.
8. Apply type conversion consistently across node and relationship writes.
9. Improve catalog generation for dbt docs support.
10. Document operational requirements for Neo4j, including APOC when graph operation macros are used.
