# tests/test_payments.py

def test_create_payment(client):
    payload = {
        "tenant_id": 1,
        "unit_id": 1,
        "amount": "25000.00",   # ✅ string instead of Decimal
        "payment_date": "2025-09-01"
    }
    response = client.post("/payments/", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["amount"] == "25000.00"
    assert data["tenant_id"] == 1
