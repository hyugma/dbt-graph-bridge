"""
Graph Bridge Connection Manager.

Manages dual connections: one to the SQL engine (RDB) and one to the
graph engine (e.g., Neo4j). SQL statements are routed to the SQL engine;
Cypher statements are routed to the graph engine.
"""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Tuple
from contextlib import contextmanager
import re

from dbt.adapters.contracts.connection import Credentials, Connection, AdapterResponse
from dbt.adapters.base.connections import BaseConnectionManager
from dbt_common.exceptions import DbtRuntimeError

from dbt.adapters.graphbridge.sql_engines import create_sql_client, SQLEngineClient
from dbt.adapters.graphbridge.graph_engines import create_graph_client, GraphEngineClient


@dataclass
class GraphBridgeCredentials(Credentials):
    """
    Credentials for dbt-graph-bridge.

    Configures two independent backends:
      1. sql_engine   – The RDB used for data transformation (duckdb, sqlalchemy)
      2. graph_engine – The graph DB used for node/relationship storage (neo4j)
    """

    # ── SQL Engine (RDB) ─────────────────────────────────────────────
    sql_engine: str = "duckdb"                   # "duckdb" | "sqlalchemy"
    sql_engine_config: Dict[str, Any] = field(default_factory=lambda: {"path": "warehouse.duckdb"})

    # ── Graph Engine ─────────────────────────────────────────────────
    graph_engine: str = "neo4j"                  # "neo4j" (future: "neptune")
    graph_scheme: str = "neo4j"
    graph_host: str = "localhost"
    graph_port: int = 7687
    graph_database: str = "neo4j"
    graph_user: str = "neo4j"
    graph_password: str = ""
    graph_encrypted: bool = False

    # ── Connection tuning ────────────────────────────────────────────
    connection_timeout: int = 30
    max_connection_lifetime: int = 3600
    max_connection_pool_size: int = 100
    connection_acquisition_timeout: int = 60

    # ── dbt required fields ──────────────────────────────────────────
    database: str = "neo4j"
    schema: str = "public"

    @property
    def type(self) -> str:
        return "graphbridge"

    @property
    def unique_field(self) -> str:
        return self.graph_host

    def _connection_keys(self) -> Tuple[str, ...]:
        return (
            "sql_engine", "graph_engine",
            "graph_host", "graph_port", "graph_database",
            "graph_user", "graph_encrypted",
        )

    @property
    def graph_uri(self) -> str:
        return f"{self.graph_scheme}://{self.graph_host}:{self.graph_port}"


# ── SQL keyword detection (comment-agnostic) ────────────────────────
_SQL_PREFIXES = ("SELECT ", "WITH ", "CREATE TABLE ", "CREATE VIEW ", "DROP ", "ALTER ", "INSERT ", "BEGIN", "COMMIT")
_COMMENT_RE = [
    re.compile(r'--.*$', re.MULTILINE),
    re.compile(r'//.*$', re.MULTILINE),
    re.compile(r'/\*.*?\*/', re.DOTALL),
]


def _is_sql(sql: str) -> bool:
    """Return True if `sql` looks like a standard SQL statement."""
    cleaned = sql
    for pattern in _COMMENT_RE:
        cleaned = pattern.sub('', cleaned)
    normalised = " ".join(cleaned.strip().upper().split())
    return any(normalised.startswith(prefix) for prefix in _SQL_PREFIXES)


class GraphBridgeConnectionManager(BaseConnectionManager):
    TYPE = "graphbridge"

    # Per-connection client instances
    _sql_client: Optional[SQLEngineClient] = None
    _graph_client: Optional[GraphEngineClient] = None

    # ── Connection lifecycle ─────────────────────────────────────────

    @classmethod
    def open(cls, connection: Connection) -> Connection:
        if connection.state == 'open':
            return connection

        credentials = connection.credentials
        try:
            graph_client = create_graph_client(credentials)
            graph_client.verify_connectivity()
            # Store both clients on the connection handle
            connection.handle = {
                "graph_client": graph_client,
                "sql_client": create_sql_client(credentials),
            }
            connection.state = 'open'
        except Exception as e:
            connection.state = 'fail'
            raise DbtRuntimeError(
                f"Failed to connect (graph_engine={credentials.graph_engine}, "
                f"sql_engine={credentials.sql_engine}): {e}"
            )
        return connection

    def _get_clients(self) -> Tuple[SQLEngineClient, GraphEngineClient]:
        conn = self.get_thread_connection()
        handle = conn.handle
        return handle["sql_client"], handle["graph_client"]

    @classmethod
    def get_response(cls, cursor) -> AdapterResponse:
        return AdapterResponse(_message="OK", code="OK")

    def cancel(self, connection: Connection) -> None:
        pass

    def begin(self) -> None:
        pass

    def commit(self) -> None:
        pass

    @classmethod
    def cancel_open(cls) -> None:
        pass

    def add_query(
        self,
        sql: str,
        auto_begin: bool = True,
        bindings: Optional[Any] = None,
        abridge_sql_log: bool = False,
    ) -> Tuple[Connection, Any]:
        response, table = self.execute(sql, auto_begin, fetch=False, bindings=bindings)
        return self.get_thread_connection(), response

    @contextmanager
    def exception_handler(self, sql: str) -> Any:
        try:
            yield
        except Exception as e:
            raise DbtRuntimeError(str(e))

    # ── Unified execute (routes SQL ↔ Cypher) ────────────────────────

    def execute(
        self,
        sql: str,
        auto_begin: bool = False,
        fetch: bool = False,
        limit: Optional[int] = None,
        bindings: Optional[Any] = None,
    ) -> Tuple[AdapterResponse, Any]:
        import agate

        sql_client, graph_client = self._get_clients()
        credentials = self.get_thread_connection().credentials

        # Intercept dbt test wrapper for Cypher queries
        # dbt generic tests wrap the content in:
        # select count(*) as failures, count(*) != 0 as should_warn, count(*) != 0 as should_error from ( <content> ) dbt_internal_test
        test_match = re.search(r"(?i)from\s*\(\s*(MATCH\s+.*?)\s*\)\s*dbt_internal_test", sql, re.DOTALL)
        if test_match:
            cypher_query = test_match.group(1).strip()
            response, records = graph_client.execute_cypher(cypher_query, parameters=bindings)
            failures = len(records)
            if fetch:
                table = agate.Table([[failures, failures != 0, failures != 0]], column_names=["failures", "should_warn", "should_error"])
                return AdapterResponse(_message="OK", code="OK"), table
            return AdapterResponse(_message="OK", code="OK"), agate.Table([])

        # Intercept main statement from graph materializations to output correct rows_affected
        rows_match = re.search(r"/\*\s*graphbridge_rows_affected:\s*(\d+)\s*\*/", sql)
        if rows_match and not _is_sql(sql):
            rows_affected = int(rows_match.group(1))
            # Just execute it to fulfill dbt, but rewrite the response
            graph_client.execute_cypher(sql, parameters=bindings)
            return AdapterResponse(_message=f"OK ({rows_affected})", code="OK", rows_affected=rows_affected), agate.Table([])

        # Route: SQL → RDB engine
        if _is_sql(sql):
            try:
                # Strip graph DB schema prefixes that dbt may inject
                clean_sql = sql.replace(f'"{credentials.database}"."{credentials.schema}".', '')

                # Rewrite CREATE TABLE → CREATE OR REPLACE TABLE (idempotent)
                upper = " ".join(clean_sql.strip().upper().split())
                if upper.startswith("CREATE TABLE "):
                    clean_sql = re.sub(
                        r'(?i)\bcreate\s+table\b',
                        'CREATE OR REPLACE TABLE',
                        clean_sql, count=1,
                    )

                if bindings:
                    # duckdb requires ? instead of %s or named bindings?
                    # actually duckdb handles parameters directly if using duckdb.execute
                    columns, rows = sql_client.execute(clean_sql, parameters=bindings)
                else:
                    columns, rows = sql_client.execute(clean_sql)
                if fetch and columns:
                    table = agate.Table(rows, column_names=columns)
                    return (
                        AdapterResponse(_message="OK", code="OK", rows_affected=len(rows)),
                        table,
                    )
                return AdapterResponse(_message="OK", code="OK"), agate.Table([])
            except Exception as e:
                import sys
                print(f"SQL Engine Error ({credentials.sql_engine}): "
                      f"{type(e).__name__} – {e}", file=sys.stderr)
                # Fall through to graph engine as last resort

        # Route: Cypher → Graph engine
        response, records = graph_client.execute_cypher(sql)
        if fetch:
            if not records:
                return response, agate.Table([])
            columns = list(records[0].keys())
            rows = [[record.get(c) for c in columns] for record in records]
            table = agate.Table(rows, column_names=columns)
            return response, table
        return response, agate.Table([])

    # ── Graph engine pass-through (used by materializations) ─────────

    def execute_cypher(
        self,
        cypher: str,
        parameters: Optional[Dict[str, Any]] = None,
        database: Optional[str] = None,
    ) -> Tuple[AdapterResponse, list]:
        _, graph_client = self._get_clients()
        return graph_client.execute_cypher(cypher, parameters, database)

    def execute_cypher_batch(
        self,
        cypher: str,
        batch_data: list,
        batch_size: int = 10000,
        database: Optional[str] = None,
    ) -> AdapterResponse:
        _, graph_client = self._get_clients()
        return graph_client.execute_cypher_batch(cypher, batch_data, batch_size, database)
