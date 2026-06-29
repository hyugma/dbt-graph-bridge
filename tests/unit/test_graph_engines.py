import pytest

from dbt.adapters.graphbridge import graph_engines


class DummyCredentials:
    graph_engine = "dummy"


class DefaultCredentials:
    pass


class DummyGraphClient:
    def __init__(self, credentials):
        self.credentials = credentials

    def verify_connectivity(self) -> None:
        pass

    def execute_cypher(self, cypher, parameters=None, database=None):
        return None, []

    def execute_cypher_batch(self, cypher, batch_data, batch_size=10000, database=None):
        return None

    def close(self) -> None:
        pass


class IncompleteGraphClient:
    def __init__(self, credentials):
        self.credentials = credentials


def test_available_graph_engines_includes_neo4j_entrypoint(monkeypatch):
    monkeypatch.setattr(
        graph_engines,
        "_load_entry_point_graph_engines",
        lambda: {"neo4j": DummyGraphClient},
    )

    assert "neo4j" in graph_engines.available_graph_engines()


def test_create_graph_client_defaults_to_neo4j_entrypoint(monkeypatch):
    monkeypatch.setattr(
        graph_engines,
        "_load_entry_point_graph_engines",
        lambda: {"neo4j": DummyGraphClient},
    )

    client = graph_engines.create_graph_client(DefaultCredentials())

    assert isinstance(client, DummyGraphClient)


def test_create_graph_client_loads_addon_factory(monkeypatch):
    monkeypatch.setattr(
        graph_engines,
        "_load_entry_point_graph_engines",
        lambda: {"dummy": DummyGraphClient},
    )

    credentials = DummyCredentials()
    client = graph_engines.create_graph_client(credentials)

    assert isinstance(client, DummyGraphClient)
    assert client.credentials is credentials


def test_create_graph_client_accepts_graphbridge_prefixed_addon(monkeypatch):
    monkeypatch.setattr(
        graph_engines,
        "_load_entry_point_graph_engines",
        lambda: {"graphbridge-dummy": DummyGraphClient},
    )

    client = graph_engines.create_graph_client(DummyCredentials())

    assert isinstance(client, DummyGraphClient)


def test_create_graph_client_reports_entry_point_group_for_missing_engine(monkeypatch):
    monkeypatch.setattr(graph_engines, "_load_entry_point_graph_engines", lambda: {})

    with pytest.raises(ValueError) as exc:
        graph_engines.create_graph_client(DummyCredentials())

    message = str(exc.value)
    assert "Unsupported graph_engine: 'dummy'" in message
    assert graph_engines.GRAPH_ENGINE_ENTRY_POINT_GROUP in message


def test_create_graph_client_validates_addon_contract(monkeypatch):
    monkeypatch.setattr(
        graph_engines,
        "_load_entry_point_graph_engines",
        lambda: {"dummy": IncompleteGraphClient},
    )

    with pytest.raises(ValueError, match="Missing methods"):
        graph_engines.create_graph_client(DummyCredentials())
