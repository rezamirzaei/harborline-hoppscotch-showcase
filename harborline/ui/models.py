from __future__ import annotations

from typing import List

from pydantic import BaseModel


class OrderItemView(BaseModel):
    sku: str
    qty: int
    unit_price: float
    line_total: float


class OrderView(BaseModel):
    id: str
    customer_id: str
    status: str
    currency: str
    total: float
    created_at: str
    updated_at: str
    items: List[OrderItemView]


class PaymentView(BaseModel):
    id: str
    order_id: str
    amount: float
    currency: str
    status: str
    created_at: str


class InventoryView(BaseModel):
    sku: str
    available: int


class DashboardView(BaseModel):
    total_orders: int
    total_revenue: float
    paid_orders: int
    recent_orders: List[OrderView]
    inventory: List[InventoryView]
