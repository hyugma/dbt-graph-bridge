"""
Graph Bridge Graph Engine Clients.

Provides the graph engine contract and entry point registry for the graph side
of the dbt-graph-bridge pipeline.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from importlib import metadata
from typing import Any, Callable, Dict, Optional, Tuple

from dbt.adapters.contracts.connection import AdapterResponse

GRAPH_ENGINE_ENTRY_POINT_GROUP = "dbt_graph_bridge.graph_engine"


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


GraphEngineFactory = Callable[[Any], GraphEngineClient]

_REQUIRED_GRAPH_CLIENT_METHODS = (
    "verify_connectivity",
    "execute_cypher",
    "execute_cypher_batch",
    "close",
)


def _normalise_graph_engine_name(name: Any) -> str:
    return str(name or "neo4j").strip().lower().replace("_", "-")


def _register_graph_engine(
    registry: Dict[str, GraphEngineFactory],
    name: str,
    factory: GraphEngineFactory,
) -> None:
    key = _normalise_graph_engine_name(name)
    registry[key] = factory

    if key.startswith("graphbridge-"):
        registry.setdefault(key.removeprefix("graphbridge-"), factory)
    else:
        registry.setdefault(f"graphbridge-{key}", factory)


def _entry_points_for_group(group: str):
    entry_points = metadata.entry_points()
    if hasattr(entry_points, "select"):
        return entry_points.select(group=group)
    return entry_points.get(group, ())


def _load_entry_point_graph_engines() -> Dict[str, GraphEngineFactory]:
    registry: Dict[str, GraphEngineFactory] = {}
    for entry_point in _entry_points_for_group(GRAPH_ENGINE_ENTRY_POINT_GROUP):
        try:
            factory = entry_point.load()
        except Exception as exc:
            raise ValueError(
                f"Failed to load graph engine add-on '{entry_point.name}' "
                f"from entry point group '{GRAPH_ENGINE_ENTRY_POINT_GROUP}': {exc}"
            ) from exc
        if not callable(factory):
            raise ValueError(
                f"Graph engine add-on '{entry_point.name}' must expose a callable "
                "factory or client class."
            )
        _register_graph_engine(registry, entry_point.name, factory)
    return registry


def _graph_engine_factories() -> Dict[str, GraphEngineFactory]:
    registry: Dict[str, GraphEngineFactory] = {}
    for name, factory in _load_entry_point_graph_engines().items():
        _register_graph_engine(registry, name, factory)
    return registry


def available_graph_engines() -> Tuple[str, ...]:
    """Return installed graph engine names."""
    return tuple(sorted(_graph_engine_factories()))


def _validate_graph_client(engine: str, client: Any) -> None:
    missing = [
        method
        for method in _REQUIRED_GRAPH_CLIENT_METHODS
        if not callable(getattr(client, method, None))
    ]
    if missing:
        raise ValueError(
            f"Graph engine '{engine}' returned an invalid client. "
            f"Missing methods: {', '.join(missing)}"
        )


def create_graph_client(credentials) -> GraphEngineClient:
    """Factory: create the appropriate graph engine client from credentials."""
    engine = getattr(credentials, "graph_engine", "neo4j")
    engine_key = _normalise_graph_engine_name(engine)
    factories = _graph_engine_factories()
    factory = factories.get(engine_key)

    if factory is None:
        supported = ", ".join(available_graph_engines()) or "none"
        raise ValueError(
            f"Unsupported graph_engine: '{engine}'. Supported or installed: {supported}. "
            f"Install a graph engine add-on that registers the "
            f"'{GRAPH_ENGINE_ENTRY_POINT_GROUP}' entry point group."
        )

    client = factory(credentials)
    _validate_graph_client(engine_key, client)
    return client
