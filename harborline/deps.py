from __future__ import annotations

from fastapi import Depends, Request

from .container import Container
from .services import (
    AuthService,
    DocumentService,
    InventoryService,
    MetricsService,
    OrderService,
    PaymentService,
    WebhookService,
)


def get_container(request: Request) -> Container:
    return request.app.state.container


def get_settings(container: Container = Depends(get_container)):
    return container.settings


def get_auth_service(container: Container = Depends(get_container)) -> AuthService:
    return container.auth_service


def get_order_service(container: Container = Depends(get_container)) -> OrderService:
    return container.order_service


def get_inventory_service(container: Container = Depends(get_container)) -> InventoryService:
    return container.inventory_service


def get_payment_service(container: Container = Depends(get_container)) -> PaymentService:
    return container.payment_service


def get_document_service(container: Container = Depends(get_container)) -> DocumentService:
    return container.document_service


def get_metrics_service(container: Container = Depends(get_container)) -> MetricsService:
    return container.metrics_service


def get_webhook_service(container: Container = Depends(get_container)) -> WebhookService:
    return container.webhook_service
