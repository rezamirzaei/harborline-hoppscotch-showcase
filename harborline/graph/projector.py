from __future__ import annotations

from typing import Optional, Protocol

from ..clock import Clock
from ..domain import Order
from .domain import OrderProjectionResult, ProjectionSource
from .store import GraphStore


class OrderProjector(Protocol):
    def project_order(self, order: Order) -> OrderProjectionResult: ...


class NoOpOrderProjector:
    def __init__(self, clock: Clock) -> None:
        self._clock = clock

    def project_order(self, order: Order) -> OrderProjectionResult:
        return OrderProjectionResult(
            order_id=order.id,
            source=ProjectionSource.DISABLED,
            projected_at=self._clock.now(),
            write={"ok": True},
        )


class GraphOrderProjector:
    def __init__(self, store: GraphStore, clock: Clock) -> None:
        self._store = store
        self._clock = clock

    def project_order(self, order: Order) -> OrderProjectionResult:
        write = self._store.upsert_order(order)
        source = ProjectionSource.GRAPH if write.ok else ProjectionSource.ERROR
        return OrderProjectionResult(
            order_id=order.id,
            source=source,
            projected_at=self._clock.now(),
            write=write,
        )

