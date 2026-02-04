from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Optional

import strawberry
from fastapi import (
    Depends,
    FastAPI,
    File,
    Header,
    HTTPException,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from strawberry.fastapi import GraphQLRouter

from .container import build_container
from .deps import (
    get_auth_service,
    get_document_service,
    get_inventory_service,
    get_metrics_service,
    get_order_service,
    get_payment_service,
    get_webhook_service,
)
from .domain import (
    AuthContext,
    CreateOrderInput,
    DocumentUploadInput,
    DocumentUploadResult,
    HealthStatus,
    InventoryLookup,
    InventoryReservation,
    InventoryReservationResult,
    InventoryItem,
    LoginRequest,
    Order,
    OrderCreate,
    OrderLookup,
    OrderQuery,
    OrderStatus,
    PartnerAuth,
    PaymentCapture,
    PaymentCaptureResult,
    PaymentIntentCreate,
    PaymentIntent,
    TokenResponse,
    TokenInput,
    WebhookReceipt,
    WebhookRequest,
)
from .errors import NotFoundError, UnauthorizedError, ValidationError
from .services import (
    AuthService,
    DocumentService,
    InventoryService,
    MetricsService,
    OrderService,
    PaymentService,
    WebhookService,
)
from .settings import Settings, load_settings
from .ui.controllers import router as ui_router

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "ui" / "static"
HOPPSCOTCH_DIR = BASE_DIR.parent / "hoppscotch"

security = HTTPBearer()


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

    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    if HOPPSCOTCH_DIR.exists():
        app.mount("/hoppscotch", StaticFiles(directory=HOPPSCOTCH_DIR), name="hoppscotch")

    app.include_router(ui_router)

    container = build_container(settings)
    app.state.container = container

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

    @app.get("/")
    async def root():
        return RedirectResponse(url="/ui")

    @app.get("/health", response_model=HealthStatus)
    async def health(metrics_service: MetricsService = Depends(get_metrics_service)):
        metrics = metrics_service.metrics()
        return HealthStatus(status="ok", time=metrics.generated_at)

    def auth_context(
        credentials: HTTPAuthorizationCredentials = Depends(security),
        auth: AuthService = Depends(get_auth_service),
    ) -> AuthContext:
        return auth.verify_token(TokenInput(token=credentials.credentials))

    def partner_auth(
        x_api_key: str = Header("", alias="X-API-Key"),
    ) -> PartnerAuth:
        if x_api_key != settings.partner_api_key:
            raise HTTPException(status_code=401, detail="Invalid partner API key")
        return PartnerAuth(api_key=x_api_key)

    @app.post("/auth/login", response_model=TokenResponse)
    async def login(payload: LoginRequest, auth: AuthService = Depends(get_auth_service)):
        return auth.login(payload)

    @app.get("/orders", response_model=list[Order])
    async def list_orders(
        status: Optional[str] = None,
        limit: int = 50,
        _: AuthContext = Depends(auth_context),
        service: OrderService = Depends(get_order_service),
    ):
        try:
            status_value = OrderStatus(status) if status else None
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid status") from exc
        result = service.list_orders(OrderQuery(status=status_value, limit=limit))
        return result.items

    @app.get("/orders/{order_id}", response_model=Order)
    async def get_order(
        order_id: str,
        _: AuthContext = Depends(auth_context),
        service: OrderService = Depends(get_order_service),
    ):
        return service.get_order(OrderLookup(order_id=order_id))

    @app.post("/orders", response_model=Order)
    async def create_order(
        payload: OrderCreate,
        idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
        _: AuthContext = Depends(auth_context),
        service: OrderService = Depends(get_order_service),
    ):
        result = service.create_order(
            CreateOrderInput(order=payload, idempotency_key=idempotency_key)
        )
        response = result.order
        if result.idempotency_replayed:
            headers = {settings.idempotency_replay_header: "true"}
            return JSONResponse(
                status_code=200,
                content=response.model_dump(mode="json"),
                headers=headers,
            )
        return response

    @app.post("/inventory/reservations", response_model=InventoryReservationResult)
    async def reserve_inventory(
        payload: InventoryReservation,
        _: PartnerAuth = Depends(partner_auth),
        service: InventoryService = Depends(get_inventory_service),
    ):
        result = service.reserve(payload)
        if result.shortages:
            raise HTTPException(
                status_code=409,
                detail={"shortages": [s.model_dump(mode="json") for s in result.shortages]},
            )
        return result

    @app.get("/inventory/sku/{sku}", response_model=InventoryItem)
    async def get_inventory(
        sku: str,
        _: AuthContext = Depends(auth_context),
        service: InventoryService = Depends(get_inventory_service),
    ):
        return service.get_inventory(InventoryLookup(sku=sku))

    @app.post("/payments/intents", response_model=PaymentIntent)
    async def create_payment_intent(
        payload: PaymentIntentCreate,
        _: AuthContext = Depends(auth_context),
        service: PaymentService = Depends(get_payment_service),
    ):
        return service.create_intent(payload)

    @app.post("/payments/capture/{payment_id}", response_model=PaymentCaptureResult)
    async def capture_payment(
        payment_id: str,
        _: AuthContext = Depends(auth_context),
        service: PaymentService = Depends(get_payment_service),
    ):
        return service.capture(PaymentCapture(payment_id=payment_id))

    @app.post("/payments/webhooks", response_model=WebhookReceipt)
    async def payment_webhook(
        request: Request,
        webhook: WebhookService = Depends(get_webhook_service),
    ):
        signature_header = request.headers.get("X-Signature", "")
        if not signature_header:
            raise HTTPException(status_code=400, detail="Missing signature")
        payload = await request.body()
        return webhook.handle(WebhookRequest(signature_header=signature_header, payload=payload))

    @app.post("/documents", response_model=DocumentUploadResult)
    async def upload_document(
        file: UploadFile = File(...),
        _: AuthContext = Depends(auth_context),
        service: DocumentService = Depends(get_document_service),
    ):
        content = await file.read()
        return service.upload(
            DocumentUploadInput(
                filename=file.filename,
                content_type=file.content_type,
                content=content,
            )
        )

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
