from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Optional

import strawberry
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from strawberry.fastapi import GraphQLRouter

from .api.rest import router as rest_router
from .container import build_container
from .domain import Order, OrderLookup, OrderQuery, OrderStatus
from .errors import NotFoundError, UnauthorizedError, ValidationError
from .graph.domain import AlsoBoughtQuery, CustomerRecommendationsQuery
from .graph.service import GraphAnalyticsService
from .middleware.rate_limit import configure_rate_limiting
from .observability import configure_observability
from .services import MetricsService, OrderService
from .settings import Settings, load_settings
from .ui.controllers import router as ui_router

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "ui" / "static"
HOPPSCOTCH_DIR = BASE_DIR.parent / "hoppscotch"


@strawberry.type
class GraphQLOrder:
    id: str
    customer_id: str
    status: str
    currency: str
    total: float
    created_at: str
    updated_at: str


@strawberry.type
class GraphQLMetrics:
    total_orders: int
    total_revenue: float
    paid_orders: int


@strawberry.type
class GraphQLProductRecommendation:
    sku: str
    score: int
    evidence: list[str]


@strawberry.type
class GraphQLCustomerRecommendations:
    customer_id: str
    source: str
    generated_at: str
    items: list[GraphQLProductRecommendation]


@strawberry.type
class GraphQLAlsoBoughtRecommendations:
    sku: str
    source: str
    generated_at: str
    items: list[GraphQLProductRecommendation]


def to_graphql_order(order: Order) -> GraphQLOrder:
    return GraphQLOrder(
        id=order.id,
        customer_id=order.customer_id,
        status=order.status.value,
        currency=order.currency,
        total=order.total,
        created_at=order.created_at.isoformat(),
        updated_at=order.updated_at.isoformat(),
    )


def graphql_schema() -> strawberry.Schema:
    @strawberry.type
    class Query:
        @strawberry.field
        def order(self, info, id: str) -> Optional[GraphQLOrder]:
            service: OrderService = info.context["container"].order_service
            try:
                order = service.get_order(OrderLookup(order_id=id))
            except NotFoundError:
                return None
            return to_graphql_order(order)

        @strawberry.field
        def orders(self, info, status: Optional[str] = None, limit: int = 50) -> list[GraphQLOrder]:
            service: OrderService = info.context["container"].order_service
            try:
                status_value = OrderStatus(status) if status else None
            except ValueError:
                status_value = None
            result = service.list_orders(OrderQuery(status=status_value, limit=limit))
            return [to_graphql_order(order) for order in result.items]

        @strawberry.field
        def metrics(self, info) -> GraphQLMetrics:
            service: MetricsService = info.context["container"].metrics_service
            metrics = service.metrics()
            return GraphQLMetrics(
                total_orders=metrics.total_orders,
                total_revenue=metrics.total_revenue,
                paid_orders=metrics.paid_orders,
            )

        @strawberry.field
        def recommendations(self, info, customer_id: str, limit: int = 10) -> GraphQLCustomerRecommendations:
            service: GraphAnalyticsService = info.context["container"].graph_analytics_service
            result = service.recommend_for_customer(CustomerRecommendationsQuery(customer_id=customer_id, limit=limit))
            return GraphQLCustomerRecommendations(
                customer_id=result.customer_id,
                source=result.source.value,
                generated_at=result.generated_at.isoformat(),
                items=[
                    GraphQLProductRecommendation(
                        sku=item.sku,
                        score=item.score,
                        evidence=item.evidence,
                    )
                    for item in result.items
                ],
            )

        @strawberry.field
        def also_bought(self, info, sku: str, limit: int = 10) -> GraphQLAlsoBoughtRecommendations:
            service: GraphAnalyticsService = info.context["container"].graph_analytics_service
            result = service.also_bought(AlsoBoughtQuery(sku=sku, limit=limit))
            return GraphQLAlsoBoughtRecommendations(
                sku=result.sku,
                source=result.source.value,
                generated_at=result.generated_at.isoformat(),
                items=[
                    GraphQLProductRecommendation(
                        sku=item.sku,
                        score=item.score,
                        evidence=item.evidence,
                    )
                    for item in result.items
                ],
            )

    return strawberry.Schema(query=Query)


def create_app(settings: Settings) -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        description="Unified commerce core for orders, payments, inventory, and real-time ops.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    configure_rate_limiting(app, settings)

    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    if HOPPSCOTCH_DIR.exists():
        app.mount("/hoppscotch", StaticFiles(directory=HOPPSCOTCH_DIR), name="hoppscotch")

    app.include_router(ui_router)

    container = build_container(settings)
    app.state.container = container

    configure_observability(app, settings, engine=container.db.engine if container.db else None)

    @app.on_event("shutdown")
    async def shutdown_event() -> None:
        if container.graph_db:
            container.graph_db.close()

    @app.exception_handler(NotFoundError)
    async def handle_not_found(_, __):
        return JSONResponse(status_code=404, content={"detail": "Not found"})

    @app.exception_handler(UnauthorizedError)
    async def handle_unauthorized(_, __):
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

    @app.exception_handler(ValidationError)
    async def handle_validation(_, exc: ValidationError):
        return JSONResponse(status_code=400, content={"detail": exc.detail})

    async def graphql_context(request: Request):
        return {"container": request.app.state.container}

    schema = graphql_schema()
    app.include_router(GraphQLRouter(schema, context_getter=graphql_context), prefix="/graphql")

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = request.headers.get(settings.request_id_header, "") or container.id_provider.new_id()
        response = await call_next(request)
        response.headers[settings.request_id_header] = request_id
        return response

    app.include_router(rest_router)
    app.include_router(rest_router, prefix="/v1")

    @app.get("/")
    async def root():
        return RedirectResponse(url="/ui")

    async def event_stream(order_id: Optional[str]):
        queue = container.event_bus.subscribe()
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                if order_id and event.payload.get("order_id") != order_id:
                    continue
                yield f"event: {event.type}\ndata: {json.dumps(event.model_dump(mode='json'))}\n\n"
        finally:
            container.event_bus.unsubscribe(queue)

    @app.get("/stream/orders")
    async def stream_orders(order_id: Optional[str] = None):
        return StreamingResponse(event_stream(order_id), media_type="text/event-stream")

    @app.websocket("/ws/shipments")
    async def ws_shipments(websocket: WebSocket):
        await websocket.accept()
        queue = container.event_bus.subscribe()
        await websocket.send_json({"type": "connected"})
        try:
            while True:
                event = await queue.get()
                await websocket.send_json(event.model_dump(mode="json"))
        except WebSocketDisconnect:
            pass
        finally:
            container.event_bus.unsubscribe(queue)

    return app


app = create_app(load_settings())
