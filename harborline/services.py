from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any, Dict, Iterable, List

import jwt

from .clock import Clock
from .domain import (
    AuthContext,
    CreateOrderInput,
    CreateOrderResult,
    DocumentUploadInput,
    DocumentUploadResult,
    EventMessage,
    EventType,
    IdempotencyRecord,
    InventoryItem,
    InventoryRequestItem,
    InventoryLookup,
    InventoryReservation,
    InventoryReservationResult,
    InventorySnapshot,
    LoginRequest,
    Metrics,
    Order,
    OrderCreate,
    OrderList,
    OrderLookup,
    OrderQuery,
    OrderStatus,
    OrderStatusUpdate,
    PaymentCapture,
    PaymentCaptureResult,
    PaymentIntent,
    PaymentIntentCreate,
    PaymentIntentList,
    PaymentStatus,
    PaymentSucceeded,
    TokenInput,
    TokenResponse,
    WebhookEvent,
    WebhookRequest,
    WebhookReceipt,
)
from .errors import NotFoundError, UnauthorizedError, ValidationError
from .id_provider import IdProvider
from .graph.projector import OrderProjector
from .repositories import EventBus, IdempotencyRepository, InventoryRepository, OrderRepository, PaymentRepository
from .settings import Settings


class AuthService:
    def __init__(self, settings: Settings, clock: Clock) -> None:
        self._settings = settings
        self._clock = clock

    def login(self, payload: LoginRequest) -> TokenResponse:
        if payload.username != self._settings.demo_user or payload.password != self._settings.demo_password:
            raise UnauthorizedError()
        token = self._encode_token(payload.username)
        return TokenResponse(access_token=token, expires_in=self._settings.token_ttl_seconds)

    def verify_token(self, payload: TokenInput) -> AuthContext:
        try:
            decoded = jwt.decode(payload.token, self._settings.jwt_secret, algorithms=["HS256"])
        except jwt.PyJWTError as exc:
            raise UnauthorizedError() from exc
        return AuthContext(**decoded)

    def _encode_token(self, username: str) -> str:
        expires = int(self._clock.now().timestamp()) + self._settings.token_ttl_seconds
        payload = {"sub": username, "iss": self._settings.jwt_issuer, "exp": expires}
        return jwt.encode(payload, self._settings.jwt_secret, algorithm="HS256")


class OrderService:
    def __init__(
        self,
        orders: OrderRepository,
        idempotency: IdempotencyRepository,
        events: EventBus,
        clock: Clock,
        ids: IdProvider,
        projector: OrderProjector,
    ) -> None:
        self._orders = orders
        self._idempotency = idempotency
        self._events = events
        self._clock = clock
        self._ids = ids
        self._projector = projector

    def create_order(self, payload: CreateOrderInput) -> CreateOrderResult:
        if payload.idempotency_key:
            cached = self._idempotency.get(payload.idempotency_key)
            if cached:
                return CreateOrderResult(order=cached.order, idempotency_replayed=True)

        order = self._build_order(payload.order)
        self._orders.add(order)
        self._projector.project_order(order)
        if payload.idempotency_key:
            self._idempotency.set(IdempotencyRecord(key=payload.idempotency_key, order=order))
        self._publish_event(EventType.ORDER_CREATED, {"order_id": order.id, "status": order.status.value})
        return CreateOrderResult(order=order)

    def list_orders(self, query: OrderQuery) -> OrderList:
        return OrderList(items=self._orders.list(query.status, query.limit))

    def get_order(self, lookup: OrderLookup) -> Order:
        order = self._orders.get(lookup.order_id)
        if not order:
            raise NotFoundError()
        return order

    def update_status(self, order: Order, status: OrderStatus) -> Order:
        updated = order.model_copy(update={"status": status, "updated_at": self._clock.now()})
        self._orders.update(updated)
        self._projector.project_order(updated)
        return updated

    def mark_paid(self, payload: PaymentSucceeded) -> OrderStatusUpdate:
        order = self._orders.get(payload.order_id)
        if order:
            self.update_status(order, OrderStatus.PAID)
        self._publish_event(
            EventType.PAYMENT_SUCCEEDED,
            {"order_id": payload.order_id, "payment_id": payload.payment_id},
        )
        return OrderStatusUpdate(order_id=payload.order_id, status=OrderStatus.PAID)

    def _build_order(self, payload: OrderCreate) -> Order:
        now = self._clock.now()
        total = round(sum(item.qty * item.unit_price for item in payload.items), 2)
        return Order(
            id=self._ids.new_id(),
            customer_id=payload.customer_id,
            status=OrderStatus.CREATED,
            currency=payload.currency,
            items=payload.items,
            total=total,
            note=payload.note,
            created_at=now,
            updated_at=now,
        )

    def _publish_event(self, event_type: EventType, payload: Dict[str, Any]) -> None:
        self._events.publish(
            EventMessage(
                id=self._ids.new_id(),
                type=event_type.value,
                timestamp=self._clock.now(),
                payload=payload,
            )
        )


class InventoryService:
    def __init__(
        self,
        inventory: InventoryRepository,
        orders: OrderRepository,
        events: EventBus,
        clock: Clock,
        ids: IdProvider,
        order_service: OrderService,
    ) -> None:
        self._inventory = inventory
        self._orders = orders
        self._events = events
        self._clock = clock
        self._ids = ids
        self._order_service = order_service

    def reserve(self, payload: InventoryReservation) -> InventoryReservationResult:
        order = self._orders.get(payload.order_id)
        if not order:
            raise NotFoundError()

        requested_items = [InventoryRequestItem(sku=item.sku, qty=item.qty) for item in payload.items]
        shortages = self._inventory.shortages(requested_items)
        if shortages:
            return InventoryReservationResult(
                order_id=payload.order_id,
                status=order.status,
                shortages=shortages,
            )

        self._inventory.reserve(requested_items)
        self._order_service.update_status(order, OrderStatus.RESERVED)
        self._publish_event(
            EventType.INVENTORY_RESERVED,
            {"order_id": payload.order_id, "status": OrderStatus.RESERVED.value},
        )
        return InventoryReservationResult(order_id=payload.order_id, status=OrderStatus.RESERVED)

    def get_inventory(self, lookup: InventoryLookup) -> InventoryItem:
        item = self._inventory.get(lookup.sku)
        if not item:
            return InventoryItem(sku=lookup.sku, available=0)
        return item

    def snapshot(self) -> InventorySnapshot:
        return InventorySnapshot(items=self._inventory.list_all())

    def _publish_event(self, event_type: EventType, payload: Dict[str, Any]) -> None:
        self._events.publish(
            EventMessage(
                id=self._ids.new_id(),
                type=event_type.value,
                timestamp=self._clock.now(),
                payload=payload,
            )
        )


class PaymentService:
    def __init__(
        self,
        payments: PaymentRepository,
        orders: OrderRepository,
        order_service: OrderService,
        events: EventBus,
        clock: Clock,
        ids: IdProvider,
    ) -> None:
        self._payments = payments
        self._orders = orders
        self._order_service = order_service
        self._events = events
        self._clock = clock
        self._ids = ids

    def create_intent(self, payload: PaymentIntentCreate) -> PaymentIntent:
        order = self._orders.get(payload.order_id)
        if not order:
            raise NotFoundError()
        if payload.amount != order.total:
            raise ValidationError("Amount mismatch")

        status = PaymentStatus.SUCCEEDED if payload.capture else PaymentStatus.REQUIRES_CAPTURE
        intent = PaymentIntent(
            id=self._ids.new_id(),
            order_id=payload.order_id,
            amount=payload.amount,
            currency=order.currency,
            status=status,
            created_at=self._clock.now(),
        )
        self._payments.add(intent)
        self._publish_event(
            EventType.PAYMENT_INTENT_CREATED,
            {"order_id": payload.order_id, "payment_id": intent.id},
        )
        return intent

    def capture(self, payload: PaymentCapture) -> PaymentCaptureResult:
        payment = self._payments.get(payload.payment_id)
        if not payment:
            raise NotFoundError()

        updated = payment.model_copy(update={"status": PaymentStatus.SUCCEEDED})
        self._payments.update(updated)
        self._order_service.mark_paid(PaymentSucceeded(order_id=updated.order_id, payment_id=updated.id))
        return PaymentCaptureResult(payment_id=updated.id, order_id=updated.order_id, status=updated.status)

    def list_payments(self) -> PaymentIntentList:
        return PaymentIntentList(items=self._payments.list_all())

    def list_by_order(self, order_id: str) -> PaymentIntentList:
        return PaymentIntentList(items=self._payments.list_by_order(order_id))

    def apply_webhook(self, payload: WebhookEvent) -> WebhookReceipt:
        if payload.type == "payment.succeeded":
            payment_id = payload.data.get("payment_id")
            order_id = payload.data.get("order_id")
            if payment_id:
                payment = self._payments.get(payment_id)
                if payment:
                    updated = payment.model_copy(update={"status": PaymentStatus.SUCCEEDED})
                    self._payments.update(updated)
            if order_id and payment_id:
                self._order_service.mark_paid(PaymentSucceeded(order_id=order_id, payment_id=payment_id))
        return WebhookReceipt(received=True)

    def _publish_event(self, event_type: EventType, payload: Dict[str, Any]) -> None:
        self._events.publish(
            EventMessage(
                id=self._ids.new_id(),
                type=event_type.value,
                timestamp=self._clock.now(),
                payload=payload,
            )
        )


class DocumentService:
    def __init__(self, settings: Settings, ids: IdProvider) -> None:
        self._settings = settings
        self._ids = ids

    def upload(self, payload: DocumentUploadInput) -> DocumentUploadResult:
        storage_key = f"{self._settings.document_prefix}/{self._ids.new_id()}"
        return DocumentUploadResult(
            filename=payload.filename,
            content_type=payload.content_type,
            size=len(payload.content),
            storage_key=storage_key,
        )


class MetricsService:
    def __init__(self, orders: OrderRepository, clock: Clock) -> None:
        self._orders = orders
        self._clock = clock

    def metrics(self) -> Metrics:
        return Metrics(
            total_orders=self._orders.count(),
            total_revenue=self._orders.total_revenue(),
            paid_orders=self._orders.paid_count(),
            generated_at=self._clock.now(),
        )


class WebhookService:
    def __init__(self, settings: Settings, payment_service: PaymentService) -> None:
        self._settings = settings
        self._payments = payment_service

    def handle(self, request: WebhookRequest) -> WebhookReceipt:
        self._verify_signature(request.signature_header, request.payload)
        event = WebhookEvent(**json.loads(request.payload.decode()))
        return self._payments.apply_webhook(event)

    def _verify_signature(self, signature_header: str, payload: bytes) -> None:
        parts: Dict[str, str] = {}
        try:
            for part in signature_header.split(","):
                if not part.strip():
                    continue
                key, value = part.strip().split("=", 1)
                parts[key] = value
        except ValueError as exc:
            raise ValidationError("Malformed signature header") from exc

        timestamp = parts.get("t", "")
        signature = parts.get("v1", "")
        signed_payload = f"{timestamp}.{payload.decode()}".encode()
        expected = hmac.new(
            self._settings.webhook_secret.encode(),
            signed_payload,
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(expected, signature):
            raise UnauthorizedError()
