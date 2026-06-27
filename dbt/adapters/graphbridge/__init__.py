from dbt.adapters.graphbridge.connections import GraphBridgeConnectionManager, GraphBridgeCredentials
from dbt.adapters.graphbridge.impl import GraphBridgeAdapter
from dbt.adapters.graphbridge.relation import GraphBridgeRelation
from dbt.adapters.graphbridge.column import GraphBridgeColumn

from dbt.adapters.base import AdapterPlugin
from dbt.include import graphbridge

Plugin = AdapterPlugin(
    adapter=GraphBridgeAdapter,
    credentials=GraphBridgeCredentials,
    include_path=graphbridge.PACKAGE_PATH,
)
