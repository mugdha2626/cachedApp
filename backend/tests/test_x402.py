"""Tests for the x402-gated /research endpoint (x402 v2).

The facilitator is always mocked — these are unit tests and must not hit
the network.
"""

import base64
import json
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

import app.x402 as x402
from app.main import app as fastapi_app

VALID_PAYMENT = {
    "x402Version": 2,
    "accepted": {
        "scheme": "exact",
        "network": "eip155:84532",
        "amount": "10000",
        "asset": x402.USDC_ADDRESS,
        "payTo": x402.SELLER_ADDRESS,
        "maxTimeoutSeconds": 60,
    },
    "payload": {"signature": "0xsig", "authorization": {"from": "0xbuyer"}},
}
VALID_HEADER = base64.b64encode(json.dumps(VALID_PAYMENT).encode()).decode()


@pytest.fixture
def client():
    return TestClient(fastapi_app)


@pytest.fixture
def facilitator_ok(monkeypatch):
    verify = AsyncMock(return_value={"isValid": True, "invalidReason": None, "payer": "0xbuyer"})
    settle = AsyncMock(
        return_value={"success": True, "errorReason": None, "transaction": "0xsettled", "network": "eip155:84532"}
    )
    monkeypatch.setattr(x402, "verify_payment", verify)
    monkeypatch.setattr(x402, "settle_payment", settle)
    return verify, settle


class TestPaymentRequired:
    def test_no_payment_header_returns_402_challenge(self, client):
        response = client.get("/research")

        assert response.status_code == 402
        body = response.json()
        assert body["x402Version"] == 2
        assert "error" not in body
        assert body["resource"]["url"].endswith("/research")
        (req,) = body["accepts"]
        assert req["scheme"] == "exact"
        assert req["network"] == "eip155:84532"
        assert req["payTo"] == x402.SELLER_ADDRESS
        assert req["asset"] == x402.USDC_ADDRESS
        assert req["amount"] == "10000"

    def test_402_body_is_mirrored_in_payment_required_header(self, client):
        response = client.get("/research")

        decoded = json.loads(base64.b64decode(response.headers["PAYMENT-REQUIRED"]))
        assert decoded == response.json()

    def test_pay_to_address_is_resolved_not_baked_in(self, client, monkeypatch):
        monkeypatch.setattr(x402, "get_payment_address", lambda resource: "0xdynamic")

        response = client.get("/research")

        assert response.json()["accepts"][0]["payTo"] == "0xdynamic"

    def test_malformed_payment_header_returns_402(self, client):
        response = client.get("/research", headers={"PAYMENT-SIGNATURE": "not-base64!!!"})

        assert response.status_code == 402
        assert "Invalid payment header" in response.json()["error"]

    def test_non_object_payment_payload_returns_402(self, client):
        header = base64.b64encode(b'"just a string"').decode()

        response = client.get("/research", headers={"PAYMENT-SIGNATURE": header})

        assert response.status_code == 402
        assert "Invalid payment header" in response.json()["error"]


class TestPaidRequest:
    def test_valid_payment_unlocks_content(self, client, facilitator_ok):
        response = client.get("/research", headers={"PAYMENT-SIGNATURE": VALID_HEADER})

        assert response.status_code == 200
        body = response.json()
        assert body["payer"] == "0xbuyer"
        assert "report" in body

    def test_v1_x_payment_header_is_also_accepted(self, client, facilitator_ok):
        response = client.get("/research", headers={"X-PAYMENT": VALID_HEADER})

        assert response.status_code == 200

    def test_settlement_is_returned_in_response_headers(self, client, facilitator_ok):
        response = client.get("/research", headers={"PAYMENT-SIGNATURE": VALID_HEADER})

        settlement = json.loads(base64.b64decode(response.headers["PAYMENT-RESPONSE"]))
        assert settlement["success"] is True
        assert settlement["transaction"] == "0xsettled"
        assert response.headers["X-PAYMENT-RESPONSE"] == response.headers["PAYMENT-RESPONSE"]

    def test_facilitator_receives_decoded_payment_and_requirements(self, client, facilitator_ok):
        verify, settle = facilitator_ok

        client.get("/research", headers={"PAYMENT-SIGNATURE": VALID_HEADER})

        payment, requirements = verify.await_args.args
        assert payment == VALID_PAYMENT
        assert requirements["payTo"] == x402.SELLER_ADDRESS
        settle.assert_awaited_once_with(payment, requirements)

    def test_invalid_payment_is_rejected_without_settling(self, client, monkeypatch):
        verify = AsyncMock(return_value={"isValid": False, "invalidReason": "insufficient_funds"})
        settle = AsyncMock()
        monkeypatch.setattr(x402, "verify_payment", verify)
        monkeypatch.setattr(x402, "settle_payment", settle)

        response = client.get("/research", headers={"PAYMENT-SIGNATURE": VALID_HEADER})

        assert response.status_code == 402
        assert response.json()["error"] == "insufficient_funds"
        settle.assert_not_awaited()

    def test_failed_settlement_returns_402(self, client, monkeypatch):
        monkeypatch.setattr(
            x402, "verify_payment", AsyncMock(return_value={"isValid": True, "payer": "0xbuyer"})
        )
        monkeypatch.setattr(
            x402, "settle_payment", AsyncMock(return_value={"success": False, "errorReason": "tx_reverted"})
        )

        response = client.get("/research", headers={"PAYMENT-SIGNATURE": VALID_HEADER})

        assert response.status_code == 402
        assert response.json()["error"] == "tx_reverted"
