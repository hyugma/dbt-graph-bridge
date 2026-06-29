from dbt.adapters.graphbridge import Plugin


def test_plugin_registered_as_graphbridge():
    assert Plugin.adapter.type() == "graphbridge"
