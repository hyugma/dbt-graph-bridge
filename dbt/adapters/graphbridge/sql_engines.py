"""
Graph Bridge SQL Engine Clients.

Provides pluggable SQL engine backends (DuckDB, SQLAlchemy-based) for the
RDB side of the dbt-graph-bridge pipeline.
"""
from __future__ import annotations

import multiprocessing
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple


class SQLEngineClient(ABC):
    """Abstract base class for SQL engine backends."""

    @abstractmethod
    def execute(self, sql: str, parameters: Optional[Any] = None) -> Tuple[List[str], List[tuple]]:
        """Execute a SQL statement and return (column_names, rows)."""
        ...

    @abstractmethod
    def close(self) -> None:
        ...


class DuckDBClient(SQLEngineClient):
    """DuckDB-backed SQL engine (embedded, zero-config)."""

    def __init__(self, path: str = ":memory:"):
        import duckdb
        self._path = path
        self._conn = duckdb.connect(database=path, read_only=False)

    def execute(self, sql: str, parameters: Optional[Any] = None) -> Tuple[List[str], List[tuple]]:
        if parameters:
            # dbt uses %s for duckdb, but duckdb uses ? natively
            sql = sql.replace("%s", "?")
            res = self._conn.execute(sql, parameters)
        else:
            res = self._conn.execute(sql)
        
        if res.description:
            columns = [desc[0] for desc in res.description]
            rows = res.fetchall()
            return columns, rows
        return [], []

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass


class SQLAlchemyClient(SQLEngineClient):
    """SQLAlchemy-backed SQL engine (Postgres, Snowflake, BigQuery, etc.)."""

    def __init__(self, connection_url: str, connect_args: Optional[dict] = None):
        from sqlalchemy import create_engine
        self._engine = create_engine(connection_url, connect_args=connect_args or {})

    def execute(self, sql: str, parameters: Optional[Any] = None) -> Tuple[List[str], List[tuple]]:
        from sqlalchemy import text
        with self._engine.connect() as conn:
            if parameters:
                result = conn.execute(text(sql), parameters)
            else:
                result = conn.execute(text(sql))
            if result.returns_rows:
                columns = list(result.keys())
                rows = result.fetchall()
                return columns, rows
            conn.commit()
            return [], []

    def close(self) -> None:
        self._engine.dispose()


@dataclass
class DbtAdapterRequiredConfig:
    credentials: Any
    project_name: str = "dbt_graph_bridge_sql_engine"
    query_comment: Any = None
    cli_vars: dict = field(default_factory=dict)
    target_path: str = "target"
    log_cache_events: bool = False
    threads: int = 1


class DbtAdapterClient(SQLEngineClient):
    """Read/query SQL engine backed by an installed dbt adapter."""

    def __init__(self, adapter_name: str, profile: dict):
        from dbt.adapters.factory import get_adapter, load_plugin, register_adapter
        from dbt_common.events.base_types import EventLevel

        try:
            credentials_cls = load_plugin(adapter_name)
        except Exception as exc:
            raise ValueError(
                f"dbt adapter '{adapter_name}' is not installed or could not be loaded. "
                f"Install the matching adapter package, for example `pip install dbt-{adapter_name}`, "
                "then rerun dbt."
            ) from exc
        credentials = credentials_cls(**profile)
        self._config = DbtAdapterRequiredConfig(credentials=credentials)

        register_adapter(
            self._config,
            multiprocessing.get_context("spawn"),
            adapter_registered_log_level=EventLevel.DEBUG,
        )
        self._adapter = get_adapter(self._config)
        self._connection_name = f"graphbridge_{adapter_name}_sql"

    def execute(self, sql: str, parameters: Optional[Any] = None) -> Tuple[List[str], List[tuple]]:
        if parameters:
            with self._adapter.connection_named(self._connection_name):
                self._adapter.connections.add_query(sql, bindings=parameters)
            return [], []
        else:
            with self._adapter.connection_named(self._connection_name):
                response, table = self._adapter.execute(sql, fetch=True)

        if table is None:
            return [], []

        columns = list(getattr(table, "column_names", []) or [])
        rows = [tuple(row) for row in table.rows]
        return columns, rows

    def close(self) -> None:
        try:
            self._adapter.cleanup_connections()
        except Exception:
            pass


def create_sql_client(credentials) -> SQLEngineClient:
    """Factory: create the appropriate SQL engine client from credentials."""
    engine = getattr(credentials, "sql_engine", "duckdb")

    if engine == "duckdb":
        path = getattr(credentials, "sql_engine_config", {}).get("path", ":memory:")
        return DuckDBClient(path=path)

    elif engine == "sqlalchemy":
        config = getattr(credentials, "sql_engine_config", {})
        url = config.get("connection_url", "")
        if not url:
            raise ValueError("sql_engine_config.connection_url is required for sqlalchemy engine")
        connect_args = config.get("connect_args", {})
        return SQLAlchemyClient(connection_url=url, connect_args=connect_args)

    elif engine == "dbt_adapter":
        config = getattr(credentials, "sql_engine_config", {})
        adapter_name = config.get("adapter")
        if not adapter_name:
            raise ValueError("sql_engine_config.adapter is required for dbt_adapter engine")
        profile = config.get("profile", {})
        if not isinstance(profile, dict):
            raise ValueError("sql_engine_config.profile must be a dictionary for dbt_adapter engine")
        return DbtAdapterClient(adapter_name=adapter_name, profile=profile)

    else:
        raise ValueError(f"Unsupported sql_engine: '{engine}'. Supported: duckdb, sqlalchemy, dbt_adapter")
