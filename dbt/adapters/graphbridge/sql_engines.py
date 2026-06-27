"""
Graph Bridge SQL Engine Clients.

Provides pluggable SQL engine backends (DuckDB, SQLAlchemy-based) for the
RDB side of the dbt-graph-bridge pipeline.
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any, List, Optional, Tuple


class SQLEngineClient(ABC):
    """Abstract base class for SQL engine backends."""

    @abstractmethod
    def execute(self, sql: str) -> Tuple[List[str], List[tuple]]:
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

    def execute(self, sql: str) -> Tuple[List[str], List[tuple]]:
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

    def execute(self, sql: str) -> Tuple[List[str], List[tuple]]:
        from sqlalchemy import text
        with self._engine.connect() as conn:
            result = conn.execute(text(sql))
            if result.returns_rows:
                columns = list(result.keys())
                rows = result.fetchall()
                return columns, rows
            conn.commit()
            return [], []

    def close(self) -> None:
        self._engine.dispose()


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

    else:
        raise ValueError(f"Unsupported sql_engine: '{engine}'. Supported: duckdb, sqlalchemy")
