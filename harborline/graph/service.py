from __future__ import annotations

from collections import Counter, defaultdict
from typing import Dict, Iterable, List, Optional, Set, Tuple

from ..clock import Clock
from ..domain import Order
from ..repositories import OrderRepository
from .domain import (
    AlsoBoughtQuery,
    AlsoBoughtRecommendations,
    CustomerRecommendations,
    CustomerRecommendationsQuery,
    ProductRecommendation,
    RecommendationSource,
)
from .store import GraphStore


class GraphAnalyticsService:
    def __init__(
        self,
        *,
        orders: OrderRepository,
        clock: Clock,
        graph_store: Optional[GraphStore] = None,
        max_orders: int = 2000,
    ) -> None:
        self._orders = orders
        self._clock = clock
        self._graph_store = graph_store
        self._max_orders = max_orders

    def recommend_for_customer(self, query: CustomerRecommendationsQuery) -> CustomerRecommendations:
        now = self._clock.now()
        if self._graph_store:
            try:
                items = self._graph_store.recommend_for_customer(query)
                if items:
                    return CustomerRecommendations(
                        customer_id=query.customer_id,
                        source=RecommendationSource.GRAPH,
                        generated_at=now,
                        items=items,
                    )
            except Exception:
                pass
        items = self._fallback_recommend_for_customer(query)
        return CustomerRecommendations(
            customer_id=query.customer_id,
            source=RecommendationSource.FALLBACK,
            generated_at=now,
            items=items,
        )

    def also_bought(self, query: AlsoBoughtQuery) -> AlsoBoughtRecommendations:
        now = self._clock.now()
        if self._graph_store:
            try:
                items = self._graph_store.also_bought(query)
                if items:
                    return AlsoBoughtRecommendations(
                        sku=query.sku,
                        source=RecommendationSource.GRAPH,
                        generated_at=now,
                        items=items,
                    )
            except Exception:
                pass
        items = self._fallback_also_bought(query)
        return AlsoBoughtRecommendations(
            sku=query.sku,
            source=RecommendationSource.FALLBACK,
            generated_at=now,
            items=items,
        )

    def _fallback_recommend_for_customer(self, query: CustomerRecommendationsQuery) -> List[ProductRecommendation]:
        orders = self._orders.list(status=None, limit=self._max_orders)
        by_customer = _group_orders_by_customer(orders)
        owned_skus = _customer_skus(by_customer.get(query.customer_id, []))
        if not owned_skus:
            return []

        related_customers = _related_customers(query.customer_id, owned_skus, orders)
        candidate_scores: Counter[str] = Counter()
        evidence: Dict[str, Set[str]] = defaultdict(set)

        for customer_id in related_customers:
            customer_orders = by_customer.get(customer_id, [])
            shared = owned_skus & _customer_skus(customer_orders)
            if not shared:
                continue
            for order in customer_orders:
                for item in order.items:
                    if item.sku in owned_skus:
                        continue
                    candidate_scores[item.sku] += 1
                    evidence[item.sku].update(shared)

        ranked = sorted(candidate_scores.items(), key=lambda it: (-it[1], it[0]))
        return [
            ProductRecommendation(sku=sku, score=score, evidence=sorted(evidence.get(sku, set())))
            for sku, score in ranked[: query.limit]
        ]

    def _fallback_also_bought(self, query: AlsoBoughtQuery) -> List[ProductRecommendation]:
        orders = self._orders.list(status=None, limit=self._max_orders)
        candidate_scores: Counter[str] = Counter()
        for order in orders:
            order_skus = {item.sku for item in order.items}
            if query.sku not in order_skus:
                continue
            for sku in order_skus:
                if sku == query.sku:
                    continue
                candidate_scores[sku] += 1

        ranked = sorted(candidate_scores.items(), key=lambda it: (-it[1], it[0]))
        return [
            ProductRecommendation(sku=sku, score=score, evidence=[query.sku]) for sku, score in ranked[: query.limit]
        ]


def _group_orders_by_customer(orders: Iterable[Order]) -> Dict[str, List[Order]]:
    grouped: Dict[str, List[Order]] = defaultdict(list)
    for order in orders:
        grouped[order.customer_id].append(order)
    return grouped


def _customer_skus(orders: Iterable[Order]) -> Set[str]:
    skus: Set[str] = set()
    for order in orders:
        for item in order.items:
            skus.add(item.sku)
    return skus


def _related_customers(target_customer_id: str, owned_skus: Set[str], orders: Iterable[Order]) -> Set[str]:
    related: Set[str] = set()
    for order in orders:
        if order.customer_id == target_customer_id:
            continue
        if any(item.sku in owned_skus for item in order.items):
            related.add(order.customer_id)
    return related

