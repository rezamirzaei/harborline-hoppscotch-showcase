from __future__ import annotations

from typing import List, Optional, Protocol

from neo4j.exceptions import Neo4jError

from ..domain import Order
from .db import GraphDb
from .domain import AlsoBoughtQuery, CustomerRecommendationsQuery, GraphWriteResult, ProductRecommendation


class GraphStore(Protocol):
    def upsert_order(self, order: Order) -> GraphWriteResult: ...

    def recommend_for_customer(self, query: CustomerRecommendationsQuery) -> List[ProductRecommendation]: ...

    def also_bought(self, query: AlsoBoughtQuery) -> List[ProductRecommendation]: ...


class Neo4jGraphStore:
    _UPSERT_ORDER = """
    MERGE (c:Customer {id: $customer_id})
    MERGE (o:Order {id: $order_id})
    SET o.currency = $currency,
        o.total = $total,
        o.status = $status,
        o.note = $note,
        o.created_at = $created_at,
        o.updated_at = $updated_at
    MERGE (c)-[:PLACED]->(o)
    WITH o
    UNWIND $items AS item
      MERGE (p:Product {sku: item.sku})
      MERGE (o)-[r:CONTAINS]->(p)
      SET r.qty = item.qty,
          r.unit_price = item.unit_price
    RETURN o.id AS order_id
    """

    _RECOMMEND_FOR_CUSTOMER = """
    MATCH (c:Customer {id: $customer_id})-[:PLACED]->(:Order)-[:CONTAINS]->(owned:Product)
    WITH c, collect(DISTINCT owned.sku) AS ownedSkus
    MATCH (c)-[:PLACED]->(:Order)-[:CONTAINS]->(shared:Product)<-[:CONTAINS]-(:Order)<-[:PLACED]-(other:Customer)
    MATCH (other)-[:PLACED]->(:Order)-[:CONTAINS]->(rec:Product)
    WHERE other.id <> c.id AND NOT rec.sku IN ownedSkus
    WITH rec.sku AS sku, collect(DISTINCT shared.sku) AS evidence, count(*) AS score
    RETURN sku, score, evidence
    ORDER BY score DESC, sku ASC
    LIMIT $limit
    """

    _ALSO_BOUGHT = """
    MATCH (p:Product {sku: $sku})<-[:CONTAINS]-(:Order)-[:CONTAINS]->(rec:Product)
    WHERE rec.sku <> $sku
    WITH rec.sku AS sku, count(*) AS score
    RETURN sku, score, [$sku] AS evidence
    ORDER BY score DESC, sku ASC
    LIMIT $limit
    """

    def __init__(self, db: GraphDb) -> None:
        self._db = db

    def upsert_order(self, order: Order) -> GraphWriteResult:
        try:
            self._db.execute_write(
                self._UPSERT_ORDER,
                {
                    "customer_id": order.customer_id,
                    "order_id": order.id,
                    "currency": order.currency,
                    "total": order.total,
                    "status": order.status.value,
                    "note": order.note,
                    "created_at": order.created_at.isoformat(),
                    "updated_at": order.updated_at.isoformat(),
                    "items": [item.model_dump() for item in order.items],
                },
            )
            return GraphWriteResult(ok=True)
        except (Neo4jError, Exception) as exc:
            return GraphWriteResult(ok=False, error=str(exc))

    def recommend_for_customer(self, query: CustomerRecommendationsQuery) -> List[ProductRecommendation]:
        rows = self._db.execute_read(
            self._RECOMMEND_FOR_CUSTOMER,
            {"customer_id": query.customer_id, "limit": query.limit},
        )
        return [_to_recommendation(row) for row in rows]

    def also_bought(self, query: AlsoBoughtQuery) -> List[ProductRecommendation]:
        rows = self._db.execute_read(
            self._ALSO_BOUGHT,
            {"sku": query.sku, "limit": query.limit},
        )
        return [_to_recommendation(row) for row in rows]


def _to_recommendation(row: dict) -> ProductRecommendation:
    evidence = row.get("evidence") or []
    evidence_list = [str(value) for value in evidence if value]
    return ProductRecommendation(
        sku=str(row.get("sku", "")),
        score=int(row.get("score") or 0),
        evidence=evidence_list,
    )
