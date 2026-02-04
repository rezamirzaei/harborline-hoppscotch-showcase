from fastapi.testclient import TestClient

from harborline.main import app


client = TestClient(app)


def test_ui_graph_seed_creates_two_orders():
    response = client.post("/ui/graph/seed")
    assert response.status_code == 200
    payload = response.json()

    assert payload["shared_sku"]
    assert payload["order_a_id"] != payload["order_b_id"]
    assert payload["customer_a_id"] != payload["customer_b_id"]
    assert len(payload["orders"]) == 2

    ids = {order["id"] for order in payload["orders"]}
    assert payload["order_a_id"] in ids
    assert payload["order_b_id"] in ids


def test_ui_realtime_simulate_runs_paid_workflow():
    response = client.post("/ui/realtime/simulate")
    assert response.status_code == 200
    payload = response.json()

    assert payload["order"]["status"] == "paid"
    assert payload["reservation_status"] == "reserved"
    assert payload["shortages"] == []
    assert payload["payment"]["status"] == "succeeded"
