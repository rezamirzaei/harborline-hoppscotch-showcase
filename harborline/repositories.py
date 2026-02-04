from __future__ import annotations

import asyncio
from typing import Dict, Iterable, List, Optional, Protocol

from .domain import (
    EventMessage,
    IdempotencyRecord,
    InventoryItem,
    InventoryRequestItem,
    InventoryShortage,
    Order,
    OrderStatus,
    PaymentIntent,
)


class OrderRepository(Protocol):
    def add(self, order: Order) -> Order: ...

    def get(self, order_id: str) -> Optional[Order]: ...

    def list(self, status: Optional[OrderStatus], limit: int) -> List[Order]: ...

    def update(self, order: Order) -> Order: ...

    def count(self) -> int: ...

    def total_revenue(self) -> float: ...

    def paid_count(self) -> int: ...


class PaymentRepository(Protocol):
    def add(self, payment: PaymentIntent) -> PaymentIntent: ...

    def get(self, payment_id: str) -> Optional[PaymentIntent]: ...

    def list_by_order(self, order_id: str) -> List[PaymentIntent]: ...

    def list_all(self) -> List[PaymentIntent]: ...

    def update(self, payment: PaymentIntent) -> PaymentIntent: ...


class InventoryRepository(Protocol):
    def get(self, sku: str) -> Optional[InventoryItem]: ...

    def list_all(self) -> List[InventoryItem]: ...

    def shortages(self, items: Iterable[InventoryRequestItem]) -> List[InventoryShortage]: ...

    def reserve(self, items: Iterable[InventoryRequestItem]) -> None: ...


class IdempotencyRepository(Protocol):
    def get(self, key: str) -> Optional[IdempotencyRecord]: ...

    def set(self, record: IdempotencyRecord) -> None: ...


class EventBus(Protocol):
    def publish(self, event: EventMessage) -> None: ...

    def subscribe(self) -> asyncio.Queue: ...

    def unsubscribe(self, queue: asyncio.Queue) -> None: ...


class InMemoryOrderRepository(OrderRepository):
    def __init__(self) -> None:
        self._orders: Dict[str, Order] = {}

    def add(self, order: Order) -> Order:
        self._orders[order.id] = order
        return order

    def get(self, order_id: str) -> Optional[Order]:
        return self._orders.get(order_id)

    def list(self, status: Optional[OrderStatus], limit: int) -> List[Order]:
        orders = list(self._orders.values())
        if status:
            orders = [order for order in orders if order.status == status]
        return orders[:limit]

    def update(self, order: Order) -> Order:
        self._orders[order.id] = order
        return order

    def count(self) -> int:
        return len(self._orders)

    def total_revenue(self) -> float:
        return round(sum(order.total for order in self._orders.values()), 2)

    def paid_count(self) -> int:
        return len([order for order in self._orders.values() if order.status == OrderStatus.PAID])


class InMemoryPaymentRepository(PaymentRepository):
    def __init__(self) -> None:
        self._payments: Dict[str, PaymentIntent] = {}

    def add(self, payment: PaymentIntent) -> PaymentIntent:
        self._payments[payment.id] = payment
        return payment

    def get(self, payment_id: str) -> Optional[PaymentIntent]:
        return self._payments.get(payment_id)

    def list_by_order(self, order_id: str) -> List[PaymentIntent]:
        return [payment for payment in self._payments.values() if payment.order_id == order_id]

    def list_all(self) -> List[PaymentIntent]:
        return list(self._payments.values())

    def update(self, payment: PaymentIntent) -> PaymentIntent:
        self._payments[payment.id] = payment
        return payment


class InMemoryInventoryRepository(InventoryRepository):
    def __init__(self, items: Iterable[InventoryItem]) -> None:
        self._inventory: Dict[str, InventoryItem] = {item.sku: item for item in items}

    def get(self, sku: str) -> Optional[InventoryItem]:
        return self._inventory.get(sku)

    def list_all(self) -> List[InventoryItem]:
        return list(self._inventory.values())

    def shortages(self, items: Iterable[InventoryRequestItem]) -> List[InventoryShortage]:
        shortages: List[InventoryShortage] = []
        for item in items:
            current = self._inventory.get(item.sku)
            available = current.available if current else 0
            if available < item.qty:
                shortages.append(
                    InventoryShortage(
                        sku=item.sku,
                        available=available,
                        requested=item.qty,
                    )
                )
        return shortages

    def reserve(self, items: Iterable[InventoryRequestItem]) -> None:
        for item in items:
            current = self._inventory.get(item.sku)
            if not current:
                self._inventory[item.sku] = InventoryItem(sku=item.sku, available=0)
                continue
            self._inventory[item.sku] = InventoryItem(
                sku=current.sku,
                available=max(current.available - item.qty, 0),
            )


class InMemoryIdempotencyRepository(IdempotencyRepository):
    def __init__(self) -> None:
        self._records: Dict[str, IdempotencyRecord] = {}

    def get(self, key: str) -> Optional[IdempotencyRecord]:
        return self._records.get(key)

    def set(self, record: IdempotencyRecord) -> None:
        self._records[record.key] = record


class InMemoryEventBus(EventBus):
    def __init__(self) -> None:
        self._subscribers: List[asyncio.Queue] = []

    def publish(self, event: EventMessage) -> None:
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                continue

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        if queue in self._subscribers:
            self._subscribers.remove(queue)
