from dataclasses import dataclass
from enum import Enum
from typing import Optional, List

from dbt.adapters.contracts.relation import RelationConfig
from dbt.adapters.base.relation import BaseRelation


class GraphBridgeRelationType(str, Enum):
    NodeLabel = "node_label"
    RelationshipType = "relationship_type"
    CypherView = "cypher_view"
    Graph = "graph"
    # Standard dbt types
    Table = "table"
    View = "view"
    CTE = "cte"
    External = "external"


@dataclass(frozen=True, eq=False, repr=False)
class GraphBridgeRelation(BaseRelation):
    type: Optional[GraphBridgeRelationType] = None
    labels: Optional[List[str]] = None
    relationship_type: Optional[str] = None
    properties_schema: Optional[dict] = None

    @property
    def is_node(self) -> bool:
        return self.type == GraphBridgeRelationType.NodeLabel

    @property
    def is_relationship(self) -> bool:
        return self.type == GraphBridgeRelationType.RelationshipType

    def render(self) -> str:
        if self.is_node and self.labels:
            return ":".join(self.labels)
        elif self.is_relationship and self.relationship_type:
            return f"[:{self.relationship_type}]"
        return self.identifier or ""

    @classmethod
    def create_from(cls, quoting, relation_config, **kwargs) -> "GraphBridgeRelation":
        config = relation_config
        materialized = config.config.get("materialized", "node")
        if materialized in ("node", "node_incremental"):
            return cls.create(
                database=config.database,
                schema=config.schema,
                identifier=config.identifier,
                type=GraphBridgeRelationType.NodeLabel,
                labels=config.config.get("labels", [config.identifier]),
            )
        elif materialized in ("relationship", "relationship_incremental"):
            return cls.create(
                database=config.database,
                schema=config.schema,
                identifier=config.identifier,
                type=GraphBridgeRelationType.RelationshipType,
                relationship_type=config.config.get("relationship_type", config.identifier),
            )
        else:
            return cls.create(
                database=config.database,
                schema=config.schema,
                identifier=config.identifier,
                type=GraphBridgeRelationType.Graph,
            )
