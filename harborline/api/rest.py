from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, File, Header, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..deps import (
    get_auth_service,
    get_document_service,
    get_inventory_service,
    get_metrics_service,
    get_order_service,
    get_payment_service,
    get_settings,
    get_webhook_service,
)
from ..domain import (
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
from ..services import (
    AuthService,
    DocumentService,
    InventoryService,
    MetricsService,
    OrderService,
    PaymentService,
    WebhookService,
)
from ..settings import Settings

security = HTTPBearer()

router = APIRouter()


def auth_context(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    auth: AuthService = Depends(get_auth_service),
) -> AuthContext:
    return auth.verify_token(TokenInput(token=credentials.credentials))


def partner_auth(
    x_api_key: str = Header("", alias="X-API-Key"),
    settings: Settings = Depends(get_settings),
) -> PartnerAuth:
    if x_api_key != settings.partner_api_key:
        raise HTTPException(status_code=401, detail="Invalid partner API key")
    return PartnerAuth(api_key=x_api_key)


@router.get("/health", response_model=HealthStatus)
async def health(metrics_service: MetricsService = Depends(get_metrics_service)):
    metrics = metrics_service.metrics()
    return HealthStatus(status="ok", time=metrics.generated_at)


@router.post("/auth/login", response_model=TokenResponse)
async def login(payload: LoginRequest, auth: AuthService = Depends(get_auth_service)):
    return auth.login(payload)


@router.get("/orders", response_model=list[Order])
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


@router.get("/orders/{order_id}", response_model=Order)
async def get_order(
    order_id: str,
    _: AuthContext = Depends(auth_context),
    service: OrderService = Depends(get_order_service),
):
    return service.get_order(OrderLookup(order_id=order_id))


@router.post("/orders", response_model=Order)
async def create_order(
    payload: OrderCreate,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    settings: Settings = Depends(get_settings),
    _: AuthContext = Depends(auth_context),
    service: OrderService = Depends(get_order_service),
):
    result = service.create_order(CreateOrderInput(order=payload, idempotency_key=idempotency_key))
    response = result.order
    if result.idempotency_replayed:
        headers = {settings.idempotency_replay_header: "true"}
        return JSONResponse(
            status_code=200,
            content=response.model_dump(mode="json"),
            headers=headers,
        )
    return response


@router.post("/inventory/reservations", response_model=InventoryReservationResult)
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


@router.get("/inventory/sku/{sku}", response_model=InventoryItem)
async def get_inventory(
    sku: str,
    _: AuthContext = Depends(auth_context),
    service: InventoryService = Depends(get_inventory_service),
):
    return service.get_inventory(InventoryLookup(sku=sku))


@router.post("/payments/intents", response_model=PaymentIntent)
async def create_payment_intent(
    payload: PaymentIntentCreate,
    _: AuthContext = Depends(auth_context),
    service: PaymentService = Depends(get_payment_service),
):
    return service.create_intent(payload)


@router.post("/payments/capture/{payment_id}", response_model=PaymentCaptureResult)
async def capture_payment(
    payment_id: str,
    _: AuthContext = Depends(auth_context),
    service: PaymentService = Depends(get_payment_service),
):
    return service.capture(PaymentCapture(payment_id=payment_id))


@router.post("/payments/webhooks", response_model=WebhookReceipt)
async def payment_webhook(
    request: Request,
    webhook: WebhookService = Depends(get_webhook_service),
):
    signature_header = request.headers.get("X-Signature", "")
    if not signature_header:
        raise HTTPException(status_code=400, detail="Missing signature")
    payload = await request.body()
    return webhook.handle(WebhookRequest(signature_header=signature_header, payload=payload))


@router.post("/documents", response_model=DocumentUploadResult)
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

