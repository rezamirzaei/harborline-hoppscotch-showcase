from __future__ import annotations

from dataclasses import dataclass

from .clock import Clock, SystemClock
from .id_provider import IdProvider, UUIDProvider
from .repositories import (
    InMemoryEventBus,
    InMemoryIdempotencyRepository,
    InMemoryInventoryRepository,
    InMemoryOrderRepository,
    InMemoryPaymentRepository,
)
from .seed import load_inventory_seed
from .services import (
    AuthService,
    DocumentService,
    InventoryService,
    MetricsService,
    OrderService,
    PaymentService,
    WebhookService,
)
from .settings import Settings


@dataclass
class Container:
    settings: Settings
    auth_service: AuthService
    order_service: OrderService
    inventory_service: InventoryService
    payment_service: PaymentService
    document_service: DocumentService
    metrics_service: MetricsService
    webhook_service: WebhookService
    event_bus: InMemoryEventBus
    clock: Clock
    id_provider: IdProvider


def build_container(settings: Settings) -> Container:
    clock = SystemClock()
    ids = UUIDProvider()

    event_bus = InMemoryEventBus()
    orders = InMemoryOrderRepository()
    payments = InMemoryPaymentRepository()
    inventory_items = load_inventory_seed(settings.inventory_seed_path)
    inventory = InMemoryInventoryRepository(inventory_items)
    idempotency = InMemoryIdempotencyRepository()

    order_service = OrderService(orders, idempotency, event_bus, clock, ids)
    inventory_service = InventoryService(inventory, orders, event_bus, clock, ids, order_service)
    payment_service = PaymentService(payments, orders, order_service, event_bus, clock, ids)
    auth_service = AuthService(settings, clock)
    document_service = DocumentService(settings, ids)
    metrics_service = MetricsService(orders, clock)
    webhook_service = WebhookService(settings, payment_service)

    return Container(
        settings=settings,
        auth_service=auth_service,
        order_service=order_service,
        inventory_service=inventory_service,
        payment_service=payment_service,
        document_service=document_service,
        metrics_service=metrics_service,
        webhook_service=webhook_service,
        event_bus=event_bus,
        clock=clock,
        id_provider=ids,
    )
