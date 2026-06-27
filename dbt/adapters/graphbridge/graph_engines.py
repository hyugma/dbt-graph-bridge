"""
Graph Bridge Graph Engine Clients.

Provides pluggable graph database backends (Neo4j, future: Neptune, Memgraph)
for the graph side of the dbt-graph-bridge pipeline.
"""
from __future__ import annotations

import datetime
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from dbt.adapters.contracts.connection import AdapterResponse


class GraphEngineClient(ABC):
    """Abstract base class for graph database backends."""

    @abstractmethod
    def verify_connectivity(self) -> None:
        ...

    @abstractmethod
    def execute_cypher(
        self,
        cypher: str,
        parameters: Optional[Dict[str, Any]] = None,
        database: Optional[str] = None,
    ) -> Tuple[AdapterResponse, list]:
        ...

    @abstractmethod
    def execute_cypher_batch(
        self,
        cypher: str,
        batch_data: list,
        batch_size: int = 10000,
        database: Optional[str] = None,
    ) -> AdapterResponse:
        ...

    @abstractmethod
    def close(self) -> None:
        ...


class Neo4jClient(GraphEngineClient):
    """Neo4j graph database backend using the official Python driver."""

    def __init__(self, credentials):
        from neo4j import GraphDatabase

        self._driver = GraphDatabase.driver(
            credentials.graph_uri,
            auth=(credentials.graph_user, credentials.graph_password),
            encrypted=getattr(credentials, "graph_encrypted", False),
            connection_timeout=getattr(credentials, "connection_timeout", 30),
            max_connection_lifetime=getattr(credentials, "max_connection_lifetime", 3600),
            max_connection_pool_size=getattr(credentials, "max_connection_pool_size", 100),
            connection_acquisition_timeout=getattr(credentials, "connection_acquisition_timeout", 60),
        )
        self._default_database = getattr(credentials, "graph_database", "neo4j")

    def verify_connectivity(self) -> None:
        self._driver.verify_connectivity()

    def execute_cypher(
        self,
        cypher: str,
        parameters: Optional[Dict[str, Any]] = None,
        database: Optional[str] = None,
    ) -> Tuple[AdapterResponse, list]:
        db = database or self._default_database
        with self._driver.session(database=db) as session:
            result = session.run(cypher, parameters=parameters or {})
            records = [dict(record) for record in result]
            summary = result.consume()

            response = AdapterResponse(
                _message=f"OK ({self._count_affected(summary)})",
                rows_affected=self._count_affected(summary),
                code="OK",
            )
            return response, records

    def execute_cypher_batch(
        self,
        cypher: str,
        batch_data: list,
        batch_size: int = 10000,
        database: Optional[str] = None,
    ) -> AdapterResponse:
        def _sanitize(val):
            if isinstance(val, Decimal):
                return float(val)
            if isinstance(val, (datetime.date, datetime.datetime)):
                return str(val)
            return val

        batch_size = batch_size or 10000
        total_affected = 0

        sanitized_batch = [
            {k: _sanitize(v) for k, v in record.items()}
            for record in batch_data
        ]

        db = database or self._default_database
        with self._driver.session(database=db) as session:
            for i in range(0, len(sanitized_batch), batch_size):
                chunk = sanitized_batch[i : i + batch_size]
                result = session.run(cypher, parameters={"batch": chunk})
                summary = result.consume()
                total_affected += self._count_affected(summary)

        return AdapterResponse(
            _message=f"OK (total: {total_affected})",
            rows_affected=total_affected,
            code="OK",
        )

    def close(self) -> None:
        try:
            self._driver.close()
        except Exception:
            pass

    @staticmethod
    def _count_affected(summary) -> int:
        c = summary.counters
        return (
            c.nodes_created + c.nodes_deleted
            + c.relationships_created + c.relationships_deleted
            + c.properties_set
        )


def create_graph_client(credentials) -> GraphEngineClient:
    """Factory: create the appropriate graph engine client from credentials."""
    engine = getattr(credentials, "graph_engine", "neo4j")

    if engine == "neo4j":
        return Neo4jClient(credentials)
    # Future: elif engine == "neptune": return NeptuneClient(credentials)
    else:
        raise ValueError(f"Unsupported graph_engine: '{engine}'. Supported: neo4j")
