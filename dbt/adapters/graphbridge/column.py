from dataclasses import dataclass
from typing import Optional, Dict

from dbt.adapters.base.column import Column


GRAPH_TYPE_MAP: Dict[str, str] = {
    "BOOLEAN": "boolean",
    "INTEGER": "integer",
    "FLOAT": "float",
    "STRING": "string",
    "DATE": "date",
    "ZONED TIME": "zoned_time",
    "LOCAL TIME": "local_time",
    "ZONED DATETIME": "zoned_datetime",
    "LOCAL DATETIME": "local_datetime",
    "DURATION": "duration",
    "POINT": "point_2d",
    "LIST": "list",
    "MAP": "map",
}

SQL_TO_GRAPH_MAP: Dict[str, str] = {
    "BOOL": "BOOLEAN",
    "BOOLEAN": "BOOLEAN",
    "INT": "INTEGER",
    "INTEGER": "INTEGER",
    "BIGINT": "INTEGER",
    "FLOAT": "FLOAT",
    "DOUBLE": "FLOAT",
    "REAL": "FLOAT",
    "VARCHAR": "STRING",
    "TEXT": "STRING",
    "DATE": "DATE",
    "TIMESTAMP": "LOCAL DATETIME",
    "TIMESTAMPTZ": "ZONED DATETIME",
    "TIME": "LOCAL TIME",
    "TIMETZ": "ZONED TIME",
    "INTERVAL": "DURATION",
    "JSON": "MAP",
    "JSONB": "MAP",
    "FLOAT[]": "LIST<FLOAT>",
}


@dataclass
class GraphBridgeColumn(Column):
    graph_type: str = "STRING"
    description: Optional[str] = None
    is_nullable: bool = True

    vector_dimensions: Optional[int] = None
    vector_similarity_function: Optional[str] = None

    @property
    def is_vector(self) -> bool:
        return self.vector_dimensions is not None

    @classmethod
    def from_sql_type(cls, name: str, sql_type: str) -> "GraphBridgeColumn":
        graph_type = SQL_TO_GRAPH_MAP.get(sql_type.upper(), "STRING")
        return cls(column=name, dtype=graph_type, graph_type=graph_type)

    def to_cypher_cast(self, variable: str) -> str:
        cast_map = {
            "DATE": f"date({variable})",
            "LOCAL DATETIME": f"localdatetime({variable})",
            "ZONED DATETIME": f"datetime({variable})",
            "LOCAL TIME": f"localtime({variable})",
            "ZONED TIME": f"time({variable})",
            "DURATION": f"duration({variable})",
            "POINT": f"point({variable})",
        }
        return cast_map.get(self.graph_type, variable)
