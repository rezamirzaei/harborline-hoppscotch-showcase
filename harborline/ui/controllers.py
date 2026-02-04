from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.status import HTTP_303_SEE_OTHER

from ..deps import (
    get_container,
    get_inventory_service,
    get_metrics_service,
    get_order_service,
    get_payment_service,
    get_settings,
)
from ..container import Container
from ..domain import (
    CreateOrderInput,
    InventoryReservation,
    OrderCreate,
    OrderItem,
    OrderLookup,
    OrderQuery,
    OrderStatus,
    PaymentCapture,
    PaymentIntentCreate,
)
from ..errors import NotFoundError, ValidationError
from ..services import InventoryService, MetricsService, OrderService, PaymentService
from ..settings import Settings
from .defaults import load_ui_defaults
from .models import (
    DashboardView,
    GraphSeedResult,
    InventoryShortageView,
    InventoryView,
    OpsSimulationResult,
    OrderItemView,
    OrderView,
    PaymentView,
)

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(BASE_DIR / "templates"))

router = APIRouter(prefix="/ui")


def build_order_items(items: List[OrderItem]) -> List[OrderItemView]:
    return [
        OrderItemView(
            sku=item.sku,
            qty=item.qty,
            unit_price=item.unit_price,
            line_total=round(item.qty * item.unit_price, 2),
        )
        for item in items
    ]


def build_order_view(order) -> OrderView:
    return OrderView(
        id=order.id,
        customer_id=order.customer_id,
        status=order.status.value,
        currency=order.currency,
        total=order.total,
        created_at=order.created_at.isoformat(),
        updated_at=order.updated_at.isoformat(),
        items=build_order_items(order.items),
    )


def build_payment_view(payment) -> PaymentView:
    return PaymentView(
        id=payment.id,
        order_id=payment.order_id,
        amount=payment.amount,
        currency=payment.currency,
        status=payment.status.value,
        created_at=payment.created_at.isoformat(),
    )


def build_dashboard_view(metrics, orders, inventory) -> DashboardView:
    recent_orders = sorted(orders, key=lambda order: order.created_at, reverse=True)[:5]
    return DashboardView(
        total_orders=metrics.total_orders,
        total_revenue=metrics.total_revenue,
        paid_orders=metrics.paid_orders,
        recent_orders=[build_order_view(order) for order in recent_orders],
        inventory=[InventoryView(sku=item.sku, available=item.available) for item in inventory],
    )


@router.get("")
async def dashboard(
    request: Request,
    metrics_service: MetricsService = Depends(get_metrics_service),
    order_service: OrderService = Depends(get_order_service),
    inventory_service: InventoryService = Depends(get_inventory_service),
):
    metrics = metrics_service.metrics()
    orders = order_service.list_orders(OrderQuery(limit=5)).items
    inventory = inventory_service.snapshot().items
    view = build_dashboard_view(metrics, orders, inventory)
    return TEMPLATES.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "view": view,
            "timestamp": metrics.generated_at.isoformat(),
        },
    )


@router.get("/orders")
async def orders(
    request: Request,
    status: Optional[str] = None,
    order_service: OrderService = Depends(get_order_service),
):
    try:
        status_value = OrderStatus(status) if status else None
    except ValueError:
        status_value = None
    query = OrderQuery(status=status_value, limit=200)
    records = order_service.list_orders(query).items
    return TEMPLATES.TemplateResponse(
        "orders.html",
        {
            "request": request,
            "orders": [build_order_view(record) for record in records],
            "status": status or "all",
        },
    )


@router.get("/orders/new")
async def new_order(
    request: Request,
    error: Optional[str] = None,
    settings: Settings = Depends(get_settings),
):
    defaults = load_ui_defaults(settings.ui_defaults_path)
    return TEMPLATES.TemplateResponse(
        "new_order.html",
        {
            "request": request,
            "error": error,
            "sample": json.dumps(defaults.order_items_sample, indent=2),
        },
    )


@router.post("/orders")
async def create_order(
    customer_id: str = Form(...),
    currency: str = Form("USD"),
    items_json: str = Form(...),
    order_service: OrderService = Depends(get_order_service),
):
    try:
        items_payload = json.loads(items_json)
        items = [OrderItem(**item) for item in items_payload]
    except (json.JSONDecodeError, TypeError, ValueError):
        return RedirectResponse(
            url="/ui/orders/new?error=invalid-json",
            status_code=HTTP_303_SEE_OTHER,
        )

    payload = CreateOrderInput(order=OrderCreate(customer_id=customer_id, currency=currency, items=items))
    result = order_service.create_order(payload)
    return RedirectResponse(url=f"/ui/orders/{result.order.id}", status_code=HTTP_303_SEE_OTHER)


@router.get("/orders/{order_id}")
async def order_detail(
    request: Request,
    order_id: str,
    error: Optional[str] = None,
    order_service: OrderService = Depends(get_order_service),
    payment_service: PaymentService = Depends(get_payment_service),
):
    try:
        record = order_service.get_order(OrderLookup(order_id=order_id))
    except NotFoundError:
        return RedirectResponse(url="/ui/orders", status_code=HTTP_303_SEE_OTHER)

    payments = payment_service.list_by_order(order_id).items
    return TEMPLATES.TemplateResponse(
        "order_detail.html",
        {
            "request": request,
            "order": build_order_view(record),
            "payments": [build_payment_view(payment) for payment in payments],
            "error": error,
        },
    )


@router.post("/orders/{order_id}/reserve")
async def reserve_order(
    order_id: str,
    order_service: OrderService = Depends(get_order_service),
    inventory_service: InventoryService = Depends(get_inventory_service),
):
    try:
        order = order_service.get_order(OrderLookup(order_id=order_id))
    except NotFoundError:
        return RedirectResponse(url="/ui/orders", status_code=HTTP_303_SEE_OTHER)

    payload = InventoryReservation(order_id=order_id, items=order.items)
    result = inventory_service.reserve(payload)
    if result.shortages:
        return RedirectResponse(
            url=f"/ui/orders/{order_id}?error=inventory",
            status_code=HTTP_303_SEE_OTHER,
        )
    return RedirectResponse(url=f"/ui/orders/{order_id}", status_code=HTTP_303_SEE_OTHER)


@router.post("/orders/{order_id}/payment-intent")
async def create_payment_intent_ui(
    order_id: str,
    capture: Optional[bool] = Form(False),
    order_service: OrderService = Depends(get_order_service),
    payment_service: PaymentService = Depends(get_payment_service),
):
    try:
        order = order_service.get_order(OrderLookup(order_id=order_id))
        payload = PaymentIntentCreate(order_id=order_id, amount=order.total, capture=bool(capture))
        intent = payment_service.create_intent(payload)
        if intent.status.value == "succeeded":
            payment_service.capture(PaymentCapture(payment_id=intent.id))
    except (NotFoundError, ValidationError):
        return RedirectResponse(url=f"/ui/orders/{order_id}", status_code=HTTP_303_SEE_OTHER)

    return RedirectResponse(url=f"/ui/orders/{order_id}", status_code=HTTP_303_SEE_OTHER)


@router.post("/payments/{payment_id}/capture")
async def capture_payment_ui(
    payment_id: str,
    payment_service: PaymentService = Depends(get_payment_service),
):
    try:
        result = payment_service.capture(PaymentCapture(payment_id=payment_id))
    except NotFoundError:
        return RedirectResponse(url="/ui/payments", status_code=HTTP_303_SEE_OTHER)

    return RedirectResponse(
        url=f"/ui/orders/{result.order_id}",
        status_code=HTTP_303_SEE_OTHER,
    )


@router.get("/inventory")
async def inventory(
    request: Request,
    inventory_service: InventoryService = Depends(get_inventory_service),
):
    items = inventory_service.snapshot().items
    return TEMPLATES.TemplateResponse(
        "inventory.html",
        {
            "request": request,
            "items": [InventoryView(sku=item.sku, available=item.available) for item in items],
        },
    )


@router.get("/payments")
async def payments(
    request: Request,
    payment_service: PaymentService = Depends(get_payment_service),
):
    records = payment_service.list_payments().items
    return TEMPLATES.TemplateResponse(
        "payments.html",
        {
            "request": request,
            "payments": [build_payment_view(payment) for payment in records],
        },
    )


@router.get("/graphql")
async def graphql_console(
    request: Request,
    settings: Settings = Depends(get_settings),
):
    defaults = load_ui_defaults(settings.ui_defaults_path)
    return TEMPLATES.TemplateResponse(
        "graphql.html",
        {
            "request": request,
            "hoppscotch_app_url": settings.hoppscotch_app_url,
            "query": defaults.graphql_query,
            "variables": json.dumps(defaults.graphql_variables, indent=2),
        },
    )


@router.get("/graph")
async def graph_insights(
    request: Request,
    container: Container = Depends(get_container),
    settings: Settings = Depends(get_settings),
    order_service: OrderService = Depends(get_order_service),
):
    defaults = load_ui_defaults(settings.ui_defaults_path)
    orders = order_service.list_orders(OrderQuery(limit=200)).items
    customer_ids = sorted({order.customer_id for order in orders})
    skus = sorted({item.sku for order in orders for item in order.items})

    reco_defaults = defaults.graph_customer_recommendations_variables or {}
    also_defaults = defaults.graph_also_bought_variables or {}

    default_customer_id = str(reco_defaults.get("customerId") or (customer_ids[0] if customer_ids else ""))
    default_customer_limit = int(reco_defaults.get("limit") or 5)
    default_sku = str(also_defaults.get("sku") or (skus[0] if skus else ""))
    default_sku_limit = int(also_defaults.get("limit") or 5)

    return TEMPLATES.TemplateResponse(
        "graph_insights.html",
        {
            "request": request,
            "hoppscotch_app_url": settings.hoppscotch_app_url,
            "graph_active": bool(container.graph_db),
            "graph_configured": bool(settings.graph_db_uri and settings.graph_db_password),
            "reco_query": defaults.graph_customer_recommendations_query,
            "also_query": defaults.graph_also_bought_query,
            "customer_ids": customer_ids,
            "skus": skus,
            "default_customer_id": default_customer_id,
            "default_customer_limit": default_customer_limit,
            "default_sku": default_sku,
            "default_sku_limit": default_sku_limit,
        },
    )


@router.post("/graph/seed", response_model=GraphSeedResult)
async def seed_graph_demo(
    container: Container = Depends(get_container),
    settings: Settings = Depends(get_settings),
    order_service: OrderService = Depends(get_order_service),
    inventory_service: InventoryService = Depends(get_inventory_service),
):
    defaults = load_ui_defaults(settings.ui_defaults_path)
    inventory = inventory_service.snapshot().items
    inventory_skus = sorted({item.sku for item in inventory})

    raw_items = defaults.order_items_sample or []
    base_items = [OrderItem(**item) for item in raw_items]
    base_skus = {item.sku for item in base_items}

    shared_sku = str((defaults.graph_also_bought_variables or {}).get("sku") or (base_items[0].sku if base_items else ""))
    if shared_sku and shared_sku not in base_skus and base_items:
        shared_sku = base_items[0].sku

    preferred_unique = "SKU-WHITE-DESK"
    unique_candidates = [sku for sku in inventory_skus if sku not in base_skus and sku != shared_sku]
    unique_sku = preferred_unique if preferred_unique in unique_candidates else (unique_candidates[0] if unique_candidates else "")

    shared_unit_price = next((item.unit_price for item in base_items if item.sku == shared_sku), None)
    fallback_price = max((item.unit_price for item in base_items), default=10.0)
    shared_unit_price = float(shared_unit_price if shared_unit_price is not None else fallback_price)

    unique_unit_price = fallback_price

    seed_suffix = container.id_provider.new_id().replace("-", "")[:8]
    customer_a_id = f"cust-a-{seed_suffix}"
    customer_b_id = f"cust-b-{seed_suffix}"

    currency = "USD"
    order_a_items = base_items or [
        OrderItem(sku=shared_sku or (inventory_skus[0] if inventory_skus else "SKU-UNKNOWN"), qty=1, unit_price=shared_unit_price)
    ]
    order_b_items = [
        OrderItem(sku=shared_sku or (inventory_skus[0] if inventory_skus else "SKU-UNKNOWN"), qty=1, unit_price=shared_unit_price),
    ]
    if unique_sku:
        order_b_items.append(OrderItem(sku=unique_sku, qty=1, unit_price=float(unique_unit_price)))

    order_a = order_service.create_order(
        CreateOrderInput(
            order=OrderCreate(
                customer_id=customer_a_id,
                currency=currency,
                items=order_a_items,
                note="Harborline insights demo seed (A)",
            )
        )
    ).order
    order_b = order_service.create_order(
        CreateOrderInput(
            order=OrderCreate(
                customer_id=customer_b_id,
                currency=currency,
                items=order_b_items,
                note="Harborline insights demo seed (B)",
            )
        )
    ).order

    return GraphSeedResult(
        shared_sku=shared_sku or unique_sku or (inventory_skus[0] if inventory_skus else ""),
        customer_a_id=customer_a_id,
        customer_b_id=customer_b_id,
        order_a_id=order_a.id,
        order_b_id=order_b.id,
        orders=[build_order_view(order_a), build_order_view(order_b)],
    )


@router.get("/realtime")
async def realtime_console(
    request: Request,
    settings: Settings = Depends(get_settings),
):
    return TEMPLATES.TemplateResponse(
        "realtime.html",
        {
            "request": request,
            "hoppscotch_app_url": settings.hoppscotch_app_url,
        },
    )


@router.post("/realtime/simulate", response_model=OpsSimulationResult)
async def simulate_ops_workflow(
    container: Container = Depends(get_container),
    settings: Settings = Depends(get_settings),
    order_service: OrderService = Depends(get_order_service),
    inventory_service: InventoryService = Depends(get_inventory_service),
    payment_service: PaymentService = Depends(get_payment_service),
):
    defaults = load_ui_defaults(settings.ui_defaults_path)
    raw_items = defaults.order_items_sample or []
    items = [OrderItem(**item) for item in raw_items] if raw_items else []
    if not items:
        inventory = inventory_service.snapshot().items
        sku = inventory[0].sku if inventory else "SKU-UNKNOWN"
        items = [OrderItem(sku=sku, qty=1, unit_price=10.0)]

    seed_suffix = container.id_provider.new_id().replace("-", "")[:8]
    customer_id = f"cust-ops-{seed_suffix}"

    created = order_service.create_order(
        CreateOrderInput(
            order=OrderCreate(
                customer_id=customer_id,
                currency="USD",
                items=items,
                note="Harborline live-ops simulation",
            )
        )
    ).order

    reservation = inventory_service.reserve(InventoryReservation(order_id=created.id, items=created.items))
    if reservation.shortages:
        return OpsSimulationResult(
            order=build_order_view(order_service.get_order(OrderLookup(order_id=created.id))),
            payment=None,
            reservation_status=reservation.status.value,
            shortages=[InventoryShortageView(**s.model_dump(mode="json")) for s in reservation.shortages],
        )

    intent = payment_service.create_intent(PaymentIntentCreate(order_id=created.id, amount=created.total, capture=False))
    capture = payment_service.capture(PaymentCapture(payment_id=intent.id))

    updated_order = order_service.get_order(OrderLookup(order_id=created.id))
    updated_payment = intent.model_copy(update={"status": capture.status})

    return OpsSimulationResult(
        order=build_order_view(updated_order),
        payment=build_payment_view(updated_payment),
        reservation_status=reservation.status.value,
        shortages=[],
    )


@router.get("/hoppscotch")
async def hoppscotch_lab(
    request: Request,
    settings: Settings = Depends(get_settings),
):
    return TEMPLATES.TemplateResponse(
        "hoppscotch.html",
        {
            "request": request,
            "hoppscotch_app_url": settings.hoppscotch_app_url,
        },
    )
