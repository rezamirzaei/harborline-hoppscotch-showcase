from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, cast


@dataclass
class GraphDb:
    uri: str
    user: str
    password: str
    database: str | None = None
    driver: Any = field(init=False)

    def __post_init__(self) -> None:
        try:
            from neo4j import GraphDatabase
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "Neo4j driver is not installed. Install `neo4j` or disable graph features (unset GRAPH_DB_URI / GRAPH_DB_PASSWORD)."
            ) from exc

        self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))

    def verify_connectivity(self) -> None:
        self.driver.verify_connectivity()

    def close(self) -> None:
        self.driver.close()

    def execute_write(self, cypher: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        params = parameters or {}
        with self.driver.session(database=self.database) as session:
            result = session.execute_write(lambda tx: tx.run(cypher, params).data())
            return cast(list[dict[str, Any]], result)

    def execute_read(self, cypher: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        params = parameters or {}
        with self.driver.session(database=self.database) as session:
            result = session.execute_read(lambda tx: tx.run(cypher, params).data())
            return cast(list[dict[str, Any]], result)

    def ensure_schema(self) -> None:
        constraints = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Customer) REQUIRE c.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (o:Order) REQUIRE o.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Product) REQUIRE p.sku IS UNIQUE",
        ]
        for statement in constraints:
            self.execute_write(statement)
