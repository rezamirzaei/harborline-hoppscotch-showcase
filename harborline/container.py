from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .clock import Clock, SystemClock
from .graph.db import GraphDb
from .graph.projector import GraphOrderProjector, NoOpOrderProjector, OrderProjector
from .graph.service import GraphAnalyticsService
from .graph.store import Neo4jGraphStore
from .id_provider import IdProvider, UUIDProvider
from .persistence.db import Database
from .persistence.repositories import (
    SqlAlchemyIdempotencyRepository,
    SqlAlchemyInventoryRepository,
    SqlAlchemyOrderRepository,
    SqlAlchemyPaymentRepository,
)
from .persistence.seed import seed_inventory_if_empty
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
    graph_analytics_service: GraphAnalyticsService
    event_bus: InMemoryEventBus
    clock: Clock
    id_provider: IdProvider
    db: Optional[Database] = None
    graph_db: Optional[GraphDb] = None


def build_container(settings: Settings) -> Container:
    clock = SystemClock()
    ids = UUIDProvider()

    event_bus = InMemoryEventBus()
    db: Optional[Database] = None
    graph_db: Optional[GraphDb] = None
    graph_store = None
    projector: OrderProjector = NoOpOrderProjector(clock)

    if settings.database_url:
        db = Database(settings.database_url, echo=settings.db_echo)
        db.create_tables()
        seed_inventory_if_empty(db, settings.inventory_seed_path)
        orders = SqlAlchemyOrderRepository(db)
        payments = SqlAlchemyPaymentRepository(db)
        inventory = SqlAlchemyInventoryRepository(db)
        idempotency = SqlAlchemyIdempotencyRepository(db)
    else:
        orders = InMemoryOrderRepository()
        payments = InMemoryPaymentRepository()
        inventory_items = load_inventory_seed(settings.inventory_seed_path)
        inventory = InMemoryInventoryRepository(inventory_items)
        idempotency = InMemoryIdempotencyRepository()

    if settings.graph_db_uri and settings.graph_db_password:
        try:
            graph_db = GraphDb(
                uri=settings.graph_db_uri,
                user=settings.graph_db_user,
                password=settings.graph_db_password,
                database=settings.graph_db_database or None,
            )
            graph_db.verify_connectivity()
            graph_db.ensure_schema()
            graph_store = Neo4jGraphStore(graph_db)
            projector = GraphOrderProjector(graph_store, clock)
        except Exception:
            graph_db = None
            graph_store = None
            projector = NoOpOrderProjector(clock)

    order_service = OrderService(orders, idempotency, event_bus, clock, ids, projector)
    inventory_service = InventoryService(inventory, orders, event_bus, clock, ids, order_service)
    payment_service = PaymentService(payments, orders, order_service, event_bus, clock, ids)
    auth_service = AuthService(settings, clock)
    document_service = DocumentService(settings, ids)
    metrics_service = MetricsService(orders, clock)
    webhook_service = WebhookService(settings, payment_service)
    graph_analytics_service = GraphAnalyticsService(
        orders=orders,
        clock=clock,
        graph_store=graph_store,
        max_orders=settings.analytics_max_orders,
    )

    return Container(
        settings=settings,
        auth_service=auth_service,
        order_service=order_service,
        inventory_service=inventory_service,
        payment_service=payment_service,
        document_service=document_service,
        metrics_service=metrics_service,
        webhook_service=webhook_service,
        graph_analytics_service=graph_analytics_service,
        event_bus=event_bus,
        clock=clock,
        id_provider=ids,
        db=db,
        graph_db=graph_db,
    )
