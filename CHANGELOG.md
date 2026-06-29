# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- Added `examples/rdb_to_neo4j` as a unified DuckDB/ClickHouse to Neo4j example using one dbt project and multiple targets.
- Added docs-only `docs_lineage` support in the unified example so dbt docs can show `companies -> stg_companies -> graph nodes -> graph relationships`.
- Added optional adapter extras for DuckDB and ClickHouse example usage.
- Added `.python-version` and moved the project requirement to Python 3.10+.

### Changed
- Documented the RDB native adapter first architecture across README and specification docs.
- Normalized the unified example's Forbes company seed headers to `snake_case` while keeping all source fields from the demo CSV.
- Consolidated the previous split DuckDB and ClickHouse examples into `examples/rdb_to_neo4j`.
- Updated the unified example so native RDB targets own seed/staging/table materialization and graphbridge targets own only graph node/relationship materialization.
- Updated example profiles to share native RDB connection values with graphbridge read backends using YAML anchors.
- Updated CI to use Python 3.10.

### Fixed
- Fixed `dbt_adapter` read-only SQL detection so SQL statements with leading dbt `-- depends_on:` comments are still recognized as read queries.
- Improved missing native dbt adapter errors for `sql_engine: dbt_adapter`.

### Validated
- Validated `dbt-duckdb` as a native RDB adapter backend for `examples/rdb_to_neo4j`.
- Validated `dbt-clickhouse` discovery/selection as a native RDB adapter backend for `examples/rdb_to_neo4j`.
- Confirmed graphbridge can read graph-ready RDB relations through installed native dbt adapters and write nodes/relationships to Neo4j/AuraDB without implementing RDB-specific DDL.
