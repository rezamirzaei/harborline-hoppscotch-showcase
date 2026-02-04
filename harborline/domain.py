from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, conint, confloat


class OrderStatus(str, Enum):
    CREATED = "created"
    RESERVED = "reserved"
    PAID = "paid"


class PaymentStatus(str, Enum):
    REQUIRES_CAPTURE = "requires_capture"
    SUCCEEDED = "succeeded"


class PaymentMethod(str, Enum):
    CARD = "card"


class EventType(str, Enum):
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
    qty: conint(gt=0)
    unit_price: confloat(gt=0)


class OrderCreate(BaseModel):
    customer_id: str
    currency: str = Field(min_length=3, max_length=3)
    items: List[OrderItem]
    note: Optional[str] = None


class Order(BaseModel):
    id: str
    customer_id: str
    status: OrderStatus
    currency: str
    items: List[OrderItem]
    total: float
    note: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class OrderList(BaseModel):
    items: List[Order]


class OrderQuery(BaseModel):
    status: Optional[OrderStatus] = None
    limit: int = 50


class OrderLookup(BaseModel):
    order_id: str


class CreateOrderInput(BaseModel):
    order: OrderCreate
    idempotency_key: Optional[str] = None


class CreateOrderResult(BaseModel):
    order: Order
    idempotency_replayed: bool = False


class OrderStatusUpdate(BaseModel):
    order_id: str
    status: OrderStatus


class InventoryReservation(BaseModel):
    order_id: str
    items: List[OrderItem]


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
    items: List[InventoryItem]


class InventoryReservationResult(BaseModel):
    order_id: str
    status: OrderStatus
    shortages: List[InventoryShortage] = Field(default_factory=list)


class InventoryLookup(BaseModel):
    sku: str


class PaymentIntentCreate(BaseModel):
    order_id: str
    amount: confloat(gt=0)
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
    items: List[PaymentIntent]


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
    data: Dict[str, Any]


class WebhookRequest(BaseModel):
    signature_header: str
    payload: bytes


class WebhookReceipt(BaseModel):
    received: bool


class DocumentUploadInput(BaseModel):
    filename: str
    content_type: Optional[str]
    content: bytes


class DocumentUploadResult(BaseModel):
    filename: str
    content_type: Optional[str]
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
    payload: Dict[str, Any]


class IdempotencyRecord(BaseModel):
    key: str
    order: Order
