from typing import Optional, List, Dict, Any, Tuple
from dbt.adapters.base import BaseAdapter, available
from dbt.adapters.graphbridge.connections import GraphBridgeConnectionManager, GraphBridgeCredentials
from dbt.adapters.graphbridge.relation import GraphBridgeRelation, GraphBridgeRelationType
from dbt.adapters.graphbridge.column import GraphBridgeColumn


class GraphBridgeAdapter(BaseAdapter):
    ConnectionManager = GraphBridgeConnectionManager
    Relation = GraphBridgeRelation
    Column = GraphBridgeColumn

    @classmethod
    def type(cls) -> str:
        return "graphbridge"

    @classmethod
    def valid_incremental_strategies(self):
        return ["merge"]

    @available
    def execute_cypher_batch(self, cypher: str, parameters: list, batch_size: int = 10000):
        self.connections.execute_cypher_batch(cypher, parameters, batch_size)

    @available
    def execute_cypher(self, cypher: str, parameters: Optional[dict] = None):
        return self.connections.execute_cypher(cypher, parameters)

    @classmethod
    def date_function(cls) -> str:
        return "date()"

    @classmethod
    def is_cancelable(cls) -> bool:
        return False

    def list_schemas(self, database: str) -> List[str]:
        return [database]

    @classmethod
    def quote(cls, identifier: str) -> str:
        return f"`{identifier}`"

    @classmethod
    def convert_text_type(cls, column: int, collation: Optional[str]) -> str:
        return "STRING"

    @classmethod
    def convert_number_type(cls, column: int, collation: Optional[str]) -> str:
        return "FLOAT"

    @classmethod
    def convert_boolean_type(cls, column: int, collation: Optional[str]) -> str:
        return "BOOLEAN"

    @classmethod
    def convert_datetime_type(cls, column: int, collation: Optional[str]) -> str:
        return "LOCAL DATETIME"

    @classmethod
    def convert_date_type(cls, column: int, collation: Optional[str]) -> str:
        return "DATE"

    @classmethod
    def convert_time_type(cls, column: int, collation: Optional[str]) -> str:
        return "LOCAL TIME"
        
    def expand_column_types(self, goal, current) -> None:
        pass

    def list_relations_without_caching(
        self, schema_relation: GraphBridgeRelation
    ) -> List[GraphBridgeRelation]:
        relations = []
        database = schema_relation.database

        # Node Labels
        _, labels = self.connections.execute_cypher(
            "CALL db.labels() YIELD label RETURN label",
            database=database,
        )
        for row in labels:
            label = row["label"]
            if not label.startswith("_dbt_"):
                relations.append(GraphBridgeRelation.create(
                    database=database,
                    identifier=label,
                    type=GraphBridgeRelationType.NodeLabel,
                    labels=[label],
                ))

        # Relationship Types
        _, types = self.connections.execute_cypher(
            "CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType",
            database=database,
        )
        for row in types:
            rel_type = row["relationshipType"]
            if not rel_type.startswith("_DBT_"):
                relations.append(GraphBridgeRelation.create(
                    database=database,
                    identifier=rel_type,
                    type=GraphBridgeRelationType.RelationshipType,
                    relationship_type=rel_type,
                ))

        return relations

    def get_columns_in_relation(
        self, relation: GraphBridgeRelation
    ) -> List[GraphBridgeColumn]:
        if relation.is_node:
            label = relation.labels[0] if relation.labels else relation.identifier
            cypher = f"""
            MATCH (n:{label})
            WITH n LIMIT 1000
            UNWIND keys(n) AS key
            WITH key, collect(DISTINCT apoc.meta.cypher.type(n[key]))[0] AS type
            RETURN key AS name, type AS graph_type
            """
        else:
            rel_type = relation.relationship_type or relation.identifier
            cypher = f"""
            MATCH ()-[r:{rel_type}]->()
            WITH r LIMIT 1000
            UNWIND keys(r) AS key
            WITH key, collect(DISTINCT apoc.meta.cypher.type(r[key]))[0] AS type
            RETURN key AS name, type AS graph_type
            """

        try:
            _, records = self.connections.execute_cypher(cypher, database=relation.database)
            return [GraphBridgeColumn(column=r["name"], dtype=r["graph_type"], graph_type=r["graph_type"]) for r in records]
        except Exception:
            return []

    def drop_relation(self, relation: GraphBridgeRelation) -> None:
        import sys
        print(f"drop_relation called for {relation.identifier} with type {relation.type}", file=sys.stderr)
        if relation.is_node:
            label = relation.labels[0] if relation.labels else relation.identifier
            cypher = f"MATCH (n:{label}) DETACH DELETE n"
        elif relation.is_relationship:
            rel_type = relation.relationship_type or relation.identifier
            cypher = f"MATCH ()-[r:{rel_type}]->() DELETE r"
        elif relation.type in (GraphBridgeRelationType.Table, GraphBridgeRelationType.View, GraphBridgeRelationType.CTE):
            # Dispatch standard SQL drop command to the SQL engine
            obj_type = "TABLE" if relation.type == GraphBridgeRelationType.Table else "VIEW"
            sql = f'DROP {obj_type} IF EXISTS "{relation.identifier}"'
            self.execute(sql)
            return
        else:
            return
        self.connections.execute_cypher(cypher, database=relation.database)

    def rename_relation(
        self, from_relation: GraphBridgeRelation, to_relation: GraphBridgeRelation
    ) -> None:
        if from_relation.is_node:
            old_label = from_relation.labels[0]
            new_label = to_relation.labels[0]
            cypher = f"""
            MATCH (n:{old_label})
            SET n:{new_label}
            REMOVE n:{old_label}
            """
            self.connections.execute_cypher(cypher, database=from_relation.database)
        elif from_relation.type == GraphBridgeRelationType.Table:
            # Drop target first to ensure idempotent rename
            drop_sql = f'DROP TABLE IF EXISTS "{to_relation.identifier}"'
            self.execute(drop_sql)
            # Dispatch standard SQL alter table command to the SQL engine
            sql = f'ALTER TABLE "{from_relation.identifier}" RENAME TO "{to_relation.identifier}"'
            self.execute(sql)

    def truncate_relation(self, relation: GraphBridgeRelation) -> None:
        self.drop_relation(relation)

    def create_schema(self, relation: GraphBridgeRelation) -> None:
        pass

    def drop_schema(self, relation: GraphBridgeRelation) -> None:
        pass

    def check_schema_exists(self, database: str, schema: str) -> bool:
        return True

    @available
    def create_indexes(self, relation: GraphBridgeRelation, indexes: List[dict]) -> None:
        for idx in indexes:
            idx_type = idx.get("type", "range")
            properties = idx["properties"]
            label = relation.labels[0] if relation.labels else relation.identifier

            if idx_type == "vector":
                cypher = f"""
                CREATE VECTOR INDEX {label}_{properties[0]}_vector IF NOT EXISTS
                FOR (n:{label}) ON (n.{properties[0]})
                OPTIONS {{indexConfig: {{
                    `vector.dimensions`: {idx['dimensions']},
                    `vector.similarity_function`: '{idx.get('similarity_function', 'cosine')}'
                }}}}
                """
            elif idx_type == "text":
                props_str = ", ".join(f"n.{p}" for p in properties)
                cypher = f"""
                CREATE TEXT INDEX {label}_{'_'.join(properties)}_text IF NOT EXISTS
                FOR (n:{label}) ON ({props_str})
                """
            else:
                props_str = ", ".join(f"n.{p}" for p in properties)
                cypher = f"""
                CREATE INDEX {label}_{'_'.join(properties)}_range IF NOT EXISTS
                FOR (n:{label}) ON ({props_str})
                """

            self.connections.execute_cypher(cypher, database=relation.database)

    @available
    def create_constraints(self, relation: GraphBridgeRelation, constraints: List[dict]) -> None:
        label = relation.labels[0] if relation.labels else relation.identifier

        for constraint in constraints:
            c_type = constraint["type"]
            props = constraint.get("properties", [])
            name = f"{label}_{'_'.join(props)}_{c_type}".lower()

            if c_type == "unique":
                props_str = ", ".join(f"n.{p}" for p in props)
                cypher = f"""
                CREATE CONSTRAINT {name} IF NOT EXISTS
                FOR (n:{label}) REQUIRE ({props_str}) IS UNIQUE
                """
            elif c_type == "not_null":
                for prop in props:
                    cypher = f"""
                    CREATE CONSTRAINT {label}_{prop}_not_null IF NOT EXISTS
                    FOR (n:{label}) REQUIRE n.{prop} IS NOT NULL
                    """
                    self.connections.execute_cypher(cypher, database=relation.database)
                continue
            elif c_type == "property_type":
                prop = constraint["property"]
                prop_type = constraint["property_type"]
                cypher = f"""
                CREATE CONSTRAINT {label}_{prop}_type IF NOT EXISTS
                FOR (n:{label}) REQUIRE n.{prop} IS :: {prop_type}
                """
            else:
                continue

            self.connections.execute_cypher(cypher, database=relation.database)

    def get_catalog(self, manifest, used_schemas) -> Tuple[Any, List[Exception]]:
        return [], []
