from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, Field

PositiveInt = Annotated[int, Field(gt=0)]
PositiveFloat = Annotated[float, Field(gt=0)]


class OrderStatus(StrEnum):
    CREATED = "created"
    RESERVED = "reserved"
    PAID = "paid"


class PaymentStatus(StrEnum):
    REQUIRES_CAPTURE = "requires_capture"
    SUCCEEDED = "succeeded"


class PaymentMethod(StrEnum):
    CARD = "card"


class EventType(StrEnum):
    ORDER_CREATED = "order.created"
    INVENTORY_RESERVED = "inventory.reserved"
    PAYMENT_INTENT_CREATED = "payment.intent_created"
    PAYMENT_SUCCEEDED = "payment.succeeded"


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int


class TokenInput(BaseModel):
    token: str


class AuthContext(BaseModel):
    sub: str
    iss: str
    exp: int


class PartnerAuth(BaseModel):
    api_key: str


class OrderItem(BaseModel):
    sku: str
    qty: PositiveInt
    unit_price: PositiveFloat


class OrderCreate(BaseModel):
    customer_id: str
    currency: str = Field(min_length=3, max_length=3)
    items: list[OrderItem]
    note: str | None = None


class Order(BaseModel):
    id: str
    customer_id: str
    status: OrderStatus
    currency: str
    items: list[OrderItem]
    total: float
    note: str | None = None
    created_at: datetime
    updated_at: datetime


class OrderList(BaseModel):
    items: list[Order]


class OrderQuery(BaseModel):
    status: OrderStatus | None = None
    limit: int = 50


class OrderLookup(BaseModel):
    order_id: str


class CreateOrderInput(BaseModel):
    order: OrderCreate
    idempotency_key: str | None = None


class CreateOrderResult(BaseModel):
    order: Order
    idempotency_replayed: bool = False


class OrderStatusUpdate(BaseModel):
    order_id: str
    status: OrderStatus


class InventoryReservation(BaseModel):
    order_id: str
    items: list[OrderItem]


class InventoryRequestItem(BaseModel):
    sku: str
    qty: int


class InventoryShortage(BaseModel):
    sku: str
    available: int
    requested: int


class InventoryItem(BaseModel):
    sku: str
    available: int


class InventorySnapshot(BaseModel):
    items: list[InventoryItem]


class InventoryReservationResult(BaseModel):
    order_id: str
    status: OrderStatus
    shortages: list[InventoryShortage] = Field(default_factory=list)


class InventoryLookup(BaseModel):
    sku: str


class PaymentIntentCreate(BaseModel):
    order_id: str
    amount: PositiveFloat
    method: PaymentMethod = PaymentMethod.CARD
    capture: bool = False


class PaymentIntent(BaseModel):
    id: str
    order_id: str
    amount: float
    currency: str
    status: PaymentStatus
    created_at: datetime


class PaymentIntentList(BaseModel):
    items: list[PaymentIntent]


class PaymentCapture(BaseModel):
    payment_id: str


class PaymentCaptureResult(BaseModel):
    payment_id: str
    order_id: str
    status: PaymentStatus


class PaymentSucceeded(BaseModel):
    order_id: str
    payment_id: str


class WebhookEvent(BaseModel):
    type: str
    data: dict[str, Any]


class WebhookRequest(BaseModel):
    signature_header: str
    payload: bytes


class WebhookReceipt(BaseModel):
    received: bool


class DocumentUploadInput(BaseModel):
    filename: str
    content_type: str | None
    content: bytes


class DocumentUploadResult(BaseModel):
    filename: str
    content_type: str | None
    size: int
    storage_key: str


class Metrics(BaseModel):
    total_orders: int
    total_revenue: float
    paid_orders: int
    generated_at: datetime


class HealthStatus(BaseModel):
    status: str
    time: datetime


class EventMessage(BaseModel):
    id: str
    type: str
    timestamp: datetime
    payload: dict[str, Any]


class IdempotencyRecord(BaseModel):
    key: str
    order: Order
