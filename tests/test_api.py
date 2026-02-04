import hmac
import hashlib
import json
import time

import pytest
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


class TestHealth:
    def test_health_returns_ok(self):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_health_includes_timestamp(self):
        response = client.get("/health")
        assert "time" in response.json()


class TestAuth:
    def test_login_success(self):
        response = client.post(
            "/auth/login",
            json={"username": settings.demo_user, "password": settings.demo_password},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "Bearer"
        assert data["expires_in"] > 0

    def test_login_invalid_credentials(self):
        response = client.post(
            "/auth/login",
            json={"username": "invalid", "password": "invalid"},
        )
        assert response.status_code == 401

    def test_protected_endpoint_without_token(self):
        response = client.get("/orders")
        # FastAPI's HTTPBearer returns 403 when no Authorization header is present
        assert response.status_code in (401, 403)

    def test_protected_endpoint_with_invalid_token(self):
        response = client.get("/orders", headers={"Authorization": "Bearer invalid_token"})
        assert response.status_code == 401


class TestOrders:
    def test_create_order_idempotent(self):
        headers = auth_headers()
        headers["Idempotency-Key"] = f"idem-{time.time()}"
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

    def test_create_order_calculates_total(self):
        headers = auth_headers()
        payload = {
            "customer_id": "cust-total-test",
            "currency": "USD",
            "items": [
                {"sku": "SKU-RED-CHAIR", "qty": 2, "unit_price": 10.0},
                {"sku": "SKU-BLUE-LAMP", "qty": 3, "unit_price": 5.0},
            ],
        }
        response = client.post("/orders", json=payload, headers=headers)
        assert response.status_code == 200
        assert response.json()["total"] == 35.0  # 2*10 + 3*5

    def test_get_order_not_found(self):
        headers = auth_headers()
        response = client.get("/orders/nonexistent-id", headers=headers)
        assert response.status_code == 404

    def test_list_orders_with_status_filter(self):
        headers = auth_headers()
        response = client.get("/orders?status=created", headers=headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_orders_invalid_status(self):
        headers = auth_headers()
        response = client.get("/orders?status=invalid", headers=headers)
        assert response.status_code == 400


class TestInventory:
    def test_inventory_reservation(self):
        token_headers = auth_headers()
        order_payload = {
            "customer_id": "cust-inv-test",
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

    def test_inventory_reservation_invalid_api_key(self):
        response = client.post(
            "/inventory/reservations",
            headers={"X-API-Key": "invalid-key"},
            json={"order_id": "test", "items": []},
        )
        assert response.status_code == 401

    def test_get_inventory_sku(self):
        headers = auth_headers()
        response = client.get("/inventory/sku/SKU-RED-CHAIR", headers=headers)
        assert response.status_code == 200
        assert "available" in response.json()


class TestPayments:
    def test_create_payment_intent(self):
        headers = auth_headers()
        order_payload = {
            "customer_id": "cust-pay-test",
            "currency": "USD",
            "items": [{"sku": "SKU-RED-CHAIR", "qty": 1, "unit_price": 10.0}],
        }
        order = client.post("/orders", json=order_payload, headers=headers).json()

        payment = client.post(
            "/payments/intents",
            json={"order_id": order["id"], "amount": 10.0, "method": "card"},
            headers=headers,
        )
        assert payment.status_code == 200
        assert payment.json()["status"] == "requires_capture"

    def test_webhook_signature(self):
        token_headers = auth_headers()
        order_payload = {
            "customer_id": "cust-webhook-test",
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

    def test_webhook_missing_signature(self):
        response = client.post(
            "/payments/webhooks",
            content="{}",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 400


class TestGraphQL:
    def test_graphql_metrics_query(self):
        query = """
        query {
            metrics {
                totalOrders
                totalRevenue
                paidOrders
            }
        }
        """
        response = client.post("/graphql", json={"query": query})
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "metrics" in data["data"]

    def test_graphql_orders_query(self):
        query = """
        query {
            orders(limit: 5) {
                id
                customerId
                status
            }
        }
        """
        response = client.post("/graphql", json={"query": query})
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "orders" in data["data"]

    def test_graphql_recommendations_query(self):
        headers = auth_headers()
        order_a = {
            "customer_id": "cust-graph-reco-a",
            "currency": "USD",
            "items": [
                {"sku": "SKU-RED-CHAIR", "qty": 1, "unit_price": 49.99},
                {"sku": "SKU-BLUE-LAMP", "qty": 1, "unit_price": 19.99},
            ],
        }
        order_b = {
            "customer_id": "cust-graph-reco-b",
            "currency": "USD",
            "items": [
                {"sku": "SKU-WHITE-DESK", "qty": 1, "unit_price": 199.0},
                {"sku": "SKU-BLUE-LAMP", "qty": 1, "unit_price": 19.99},
            ],
        }
        assert client.post("/orders", json=order_a, headers=headers).status_code == 200
        assert client.post("/orders", json=order_b, headers=headers).status_code == 200

        query = """
        query Recommendations($customerId: String!, $limit: Int!) {
            recommendations(customerId: $customerId, limit: $limit) {
                customerId
                source
                items {
                    sku
                    score
                    evidence
                }
            }
        }
        """
        response = client.post(
            "/graphql",
            json={"query": query, "variables": {"customerId": "cust-graph-reco-a", "limit": 50}},
        )
        assert response.status_code == 200
        payload = response.json()
        recos = payload["data"]["recommendations"]
        assert recos["customerId"] == "cust-graph-reco-a"
        assert recos["source"] in ("graph", "fallback")
        skus = [item["sku"] for item in recos["items"]]
        assert "SKU-WHITE-DESK" in skus
        desk = next(item for item in recos["items"] if item["sku"] == "SKU-WHITE-DESK")
        assert "SKU-BLUE-LAMP" in desk["evidence"]

    def test_graphql_also_bought_query(self):
        headers = auth_headers()
        order_a = {
            "customer_id": "cust-also-bought-a",
            "currency": "USD",
            "items": [
                {"sku": "SKU-RED-CHAIR", "qty": 1, "unit_price": 49.99},
                {"sku": "SKU-BLUE-LAMP", "qty": 1, "unit_price": 19.99},
            ],
        }
        order_b = {
            "customer_id": "cust-also-bought-b",
            "currency": "USD",
            "items": [
                {"sku": "SKU-WHITE-DESK", "qty": 1, "unit_price": 199.0},
                {"sku": "SKU-BLUE-LAMP", "qty": 1, "unit_price": 19.99},
            ],
        }
        assert client.post("/orders", json=order_a, headers=headers).status_code == 200
        assert client.post("/orders", json=order_b, headers=headers).status_code == 200

        query = """
        query AlsoBought($sku: String!, $limit: Int!) {
            alsoBought(sku: $sku, limit: $limit) {
                sku
                source
                items {
                    sku
                    score
                    evidence
                }
            }
        }
        """
        response = client.post(
            "/graphql",
            json={"query": query, "variables": {"sku": "SKU-BLUE-LAMP", "limit": 50}},
        )
        assert response.status_code == 200
        payload = response.json()
        data = payload["data"]["alsoBought"]
        assert data["sku"] == "SKU-BLUE-LAMP"
        assert data["source"] in ("graph", "fallback")
        skus = [item["sku"] for item in data["items"]]
        assert "SKU-RED-CHAIR" in skus
        assert "SKU-WHITE-DESK" in skus


# Keep backwards compatibility with old test names
def test_health():
    TestHealth().test_health_returns_ok()

def test_create_order_idempotent():
    TestOrders().test_create_order_idempotent()

def test_inventory_reservation():
    TestInventory().test_inventory_reservation()

def test_webhook_signature():
    TestPayments().test_webhook_signature()
