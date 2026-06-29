# rdb_to_neo4j

Unified dbt example for the RDB native adapter first workflow.

The same seed, staging model, graph node models, and graph relationship models can be run against either DuckDB or ClickHouse on the relational side. `dbt-graph-bridge` then reads the already-built relational staging table and writes the graph to Neo4j.

## Shape

- `duckdb_dev`: builds seeds and staging tables with `dbt-duckdb`
- `clickhouse_dev`: builds seeds and staging tables with `dbt-clickhouse`
- `neo4j_from_duckdb`: reads DuckDB staging tables and writes graph resources
- `neo4j_from_clickhouse`: reads ClickHouse staging tables and writes graph resources

Use `--target` to switch the active connection. The project keeps a single `profile` name: `rdb_to_neo4j`.

## Source Data

The Forbes company seed is stored at `seeds/companies.csv`.

The seed keeps all fields from the demo CSV and normalizes field names to `snake_case`, for example:

- `companyName` -> `company_name`
- `marketValue` -> `market_value`
- `profitsRank` -> `profits_rank`
- `ceoName` -> `ceo_name`
- `yearFounded` -> `year_founded`
- `webSite` -> `web_site`

The current CSV does not include parent-company fields, so this unified example creates company, industry, location, and CEO relationships, but not `SUBSIDIARY_OF`.

## Requirements

- `dbt-core`
- `dbt-graph-bridge`
- `dbt-duckdb`
- `dbt-clickhouse`
- A ClickHouse server if running the ClickHouse path
- A Neo4j or AuraDB instance for graph writes

From this repository, the example dependencies can be installed with:

```bash
pip install -e ".[examples]"
```

## Environment

DuckDB:

```bash
export DBT_GRAPHBRIDGE_DUCKDB_PATH="warehouse.duckdb"
```

ClickHouse:

```bash
export DBT_GRAPHBRIDGE_CLICKHOUSE_HOST="localhost"
export DBT_GRAPHBRIDGE_CLICKHOUSE_PORT="8123"
export DBT_GRAPHBRIDGE_CLICKHOUSE_SCHEMA="default"
export DBT_GRAPHBRIDGE_CLICKHOUSE_USER="default"
export DBT_GRAPHBRIDGE_CLICKHOUSE_PASSWORD=""
export DBT_GRAPHBRIDGE_CLICKHOUSE_SECURE="False"
export DBT_GRAPHBRIDGE_CLICKHOUSE_DRIVER="http"
```

For ClickHouse Cloud, keep `DBT_GRAPHBRIDGE_CLICKHOUSE_DRIVER="http"`, set `DBT_GRAPHBRIDGE_CLICKHOUSE_SECURE="True"`, and use the HTTPS port shown in the ClickHouse Cloud connection dialog, commonly `8443`.

Neo4j:

```bash
export DBT_GRAPHBRIDGE_GRAPH_HOST="..."
export DBT_GRAPHBRIDGE_GRAPH_DATABASE="..."
export DBT_GRAPHBRIDGE_GRAPH_USER="..."
export DBT_GRAPHBRIDGE_GRAPH_PASSWORD="..."
export DBT_GRAPHBRIDGE_GRAPH_SCHEME="neo4j+s"
export DBT_GRAPHBRIDGE_GRAPH_PORT="7687"
```

## DuckDB To Neo4j

```bash
cd examples/rdb_to_neo4j
dbt seed --profiles-dir . --target duckdb_dev --full-refresh
dbt run --profiles-dir . --target duckdb_dev
dbt run --profiles-dir . --target neo4j_from_duckdb
```

## ClickHouse To Neo4j

```bash
cd examples/rdb_to_neo4j
dbt seed --profiles-dir . --target clickhouse_dev --full-refresh
dbt run --profiles-dir . --target clickhouse_dev
dbt run --profiles-dir . --target neo4j_from_clickhouse
```

When a graphbridge target is used, staging models are disabled and graphbridge runs only graph node and relationship models. Run the matching native RDB target first so `stg_companies` exists in that RDB.

## Expected Graph Output

- Nodes: `Company`, `Industry`, `City`, `Country`, `CEO:Person`
- Relationships: `BELONGS_TO`, `HEADQUARTERED_IN`, `LED_BY`, `LOCATED_IN`

If you run both DuckDB and ClickHouse paths into the same Neo4j database, clear the graph or use a separate database between runs when you want to compare outputs independently.

## dbt Docs

Generate docs for the relational phase with the native RDB target:

```bash
cd examples/rdb_to_neo4j
dbt build --profiles-dir . --target duckdb_dev --full-refresh
dbt docs generate --profiles-dir . --target duckdb_dev
dbt docs serve
```

For ClickHouse:

```bash
dbt build --profiles-dir . --target clickhouse_dev --full-refresh
dbt docs generate --profiles-dir . --target clickhouse_dev
dbt docs serve
```

Graphbridge targets can also generate docs for graph models, but they need valid Neo4j and RDB connection environment variables because the adapter opens both sides of the bridge:

```bash
dbt docs generate --profiles-dir . --target neo4j_from_duckdb
dbt docs serve
```

To see end-to-end lineage from the RDB transformation into graph materializations, enable the docs-only lineage mode:

```bash
dbt docs generate --profiles-dir . --target neo4j_from_duckdb --vars '{docs_lineage: true}'
dbt docs serve
```

This includes `stg_companies` in the graphbridge manifest and adds docs-only dependencies from graph models back to the staging table. Do not use `docs_lineage: true` with `dbt run`; it is intended for docs generation and lineage inspection.

Use `--target-path` if you want to keep separate docs artifacts for RDB and graph targets.
