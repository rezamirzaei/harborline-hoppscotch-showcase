from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from neo4j import Driver, GraphDatabase


@dataclass
class GraphDb:
    uri: str
    user: str
    password: str
    database: Optional[str] = None
    driver: Driver = field(init=False)

    def __post_init__(self) -> None:
        self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))

    def verify_connectivity(self) -> None:
        self.driver.verify_connectivity()

    def close(self) -> None:
        self.driver.close()

    def execute_write(self, cypher: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        params = parameters or {}
        with self.driver.session(database=self.database) as session:
            return session.execute_write(lambda tx: tx.run(cypher, params).data())

    def execute_read(self, cypher: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        params = parameters or {}
        with self.driver.session(database=self.database) as session:
            return session.execute_read(lambda tx: tx.run(cypher, params).data())

    def ensure_schema(self) -> None:
        constraints = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Customer) REQUIRE c.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (o:Order) REQUIRE o.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Product) REQUIRE p.sku IS UNIQUE",
        ]
        for statement in constraints:
            self.execute_write(statement)

