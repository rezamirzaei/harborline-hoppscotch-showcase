import hmac
import hashlib
import json
import time

from fastapi.testclient import TestClient

from harborline.main import app
from harborline.settings import load_settings

settings = load_settings()
PARTNER_API_KEY = settings.partner_api_key
WEBHOOK_SECRET = settings.webhook_secret

client = TestClient(app)


def login_token() -> str:
    response = client.post(
        "/auth/login",
        json={"username": settings.demo_user, "password": settings.demo_password},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["access_token"]
    return data["access_token"]


def auth_headers() -> dict:
    token = login_token()
    return {"Authorization": f"Bearer {token}"}


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_create_order_idempotent():
    headers = auth_headers()
    headers["Idempotency-Key"] = "idem-001"
    payload = {
        "customer_id": "cust-001",
        "currency": "USD",
        "items": [
            {"sku": "SKU-RED-CHAIR", "qty": 2, "unit_price": 49.99},
            {"sku": "SKU-BLUE-LAMP", "qty": 1, "unit_price": 19.99},
        ],
    }
    first = client.post("/orders", json=payload, headers=headers)
    assert first.status_code == 200

    second = client.post("/orders", json=payload, headers=headers)
    assert second.status_code == 200
    assert second.headers.get("Idempotency-Replayed") == "true"
    assert first.json()["id"] == second.json()["id"]


def test_inventory_reservation():
    token_headers = auth_headers()
    order_payload = {
        "customer_id": "cust-002",
        "currency": "USD",
        "items": [{"sku": "SKU-WHITE-DESK", "qty": 1, "unit_price": 199.0}],
    }
    order = client.post("/orders", json=order_payload, headers=token_headers).json()

    reservation = client.post(
        "/inventory/reservations",
        headers={"X-API-Key": PARTNER_API_KEY},
        json={"order_id": order["id"], "items": order_payload["items"]},
    )
    assert reservation.status_code == 200
    assert reservation.json()["status"] == "reserved"


def test_webhook_signature():
    token_headers = auth_headers()
    order_payload = {
        "customer_id": "cust-003",
        "currency": "USD",
        "items": [{"sku": "SKU-RED-CHAIR", "qty": 1, "unit_price": 10.0}],
    }
    order = client.post("/orders", json=order_payload, headers=token_headers).json()
    payment = client.post(
        "/payments/intents",
        json={"order_id": order["id"], "amount": 10.0, "method": "card"},
        headers=token_headers,
    ).json()

    payload = {
        "type": "payment.succeeded",
        "data": {"order_id": order["id"], "payment_id": payment["id"]},
    }
    raw = json.dumps(payload)
    timestamp = str(int(time.time()))
    signed_payload = f"{timestamp}.{raw}".encode()
    signature = hmac.new(WEBHOOK_SECRET.encode(), signed_payload, hashlib.sha256).hexdigest()

    response = client.post(
        "/payments/webhooks",
        content=raw,
        headers={"X-Signature": f"t={timestamp},v1={signature}", "Content-Type": "application/json"},
    )
    assert response.status_code == 200
    assert response.json()["received"] is True
