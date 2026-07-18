"""Tests for the FastAPI app: hello world + seller registration.

CDP is always mocked — these are unit tests and must not hit the network
or require real credentials.
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import app.wallet as wallet
from app.main import app as fastapi_app

CDP_ENV = ["CDP_API_KEY_ID", "CDP_API_KEY_SECRET", "CDP_WALLET_SECRET"]
FAKE_ADDRESS = "0x1111111111111111111111111111111111111111"
FAKE_FAUCET_TX = "0xfaucettx"


@pytest.fixture
def client():
    return TestClient(fastapi_app)


@pytest.fixture
def cdp_env(monkeypatch):
    for key in CDP_ENV:
        monkeypatch.setenv(key, "test-value")


@pytest.fixture
def no_cdp_env(monkeypatch):
    for key in CDP_ENV:
        monkeypatch.delenv(key, raising=False)


def make_fake_cdp(faucet_error: Exception | None = None) -> MagicMock:
    """Build a fake CdpClient class usable as an async context manager."""
    account = MagicMock()
    account.address = FAKE_ADDRESS

    cdp = MagicMock()
    cdp.evm.get_or_create_account = AsyncMock(return_value=account)
    if faucet_error is None:
        cdp.evm.request_faucet = AsyncMock(return_value=FAKE_FAUCET_TX)
    else:
        cdp.evm.request_faucet = AsyncMock(side_effect=faucet_error)

    fake_class = MagicMock()
    fake_class.return_value.__aenter__ = AsyncMock(return_value=cdp)
    fake_class.return_value.__aexit__ = AsyncMock(return_value=False)
    fake_class.cdp = cdp  # expose for assertions
    return fake_class


class TestHello:
    def test_hello_world(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert response.json() == {"message": "Hello, world!"}


class TestRegister:
    def test_register_returns_wallet(self, client, cdp_env, monkeypatch):
        fake = make_fake_cdp()
        monkeypatch.setattr(wallet, "CdpClient", fake)

        response = client.post("/register")

        assert response.status_code == 200
        body = response.json()
        assert body["address"] == FAKE_ADDRESS
        assert body["network"] == "eip155:84532"
        assert body["name"] == wallet.ACCOUNT_NAME
        assert body["faucet_tx"] == FAKE_FAUCET_TX

    def test_register_is_idempotent_get_or_create(self, client, cdp_env, monkeypatch):
        fake = make_fake_cdp()
        monkeypatch.setattr(wallet, "CdpClient", fake)

        client.post("/register")

        fake.cdp.evm.get_or_create_account.assert_awaited_once_with(name=wallet.ACCOUNT_NAME)

    def test_register_requests_usdc_faucet_on_base_sepolia(self, client, cdp_env, monkeypatch):
        fake = make_fake_cdp()
        monkeypatch.setattr(wallet, "CdpClient", fake)

        client.post("/register")

        fake.cdp.evm.request_faucet.assert_awaited_once_with(
            address=FAKE_ADDRESS, network="base-sepolia", token="usdc"
        )

    def test_register_succeeds_when_faucet_fails(self, client, cdp_env, monkeypatch):
        fake = make_fake_cdp(faucet_error=RuntimeError("faucet rate limited"))
        monkeypatch.setattr(wallet, "CdpClient", fake)

        response = client.post("/register")

        assert response.status_code == 200
        assert response.json()["address"] == FAKE_ADDRESS
        assert response.json()["faucet_tx"] is None

    def test_register_without_credentials_returns_503(self, client, no_cdp_env):
        response = client.post("/register")

        assert response.status_code == 503
        detail = response.json()["detail"]
        for key in CDP_ENV:
            assert key in detail

    def test_register_reports_only_missing_credentials(self, client, no_cdp_env, monkeypatch):
        monkeypatch.setenv("CDP_API_KEY_ID", "present")

        response = client.post("/register")

        assert response.status_code == 503
        detail = response.json()["detail"]
        assert "CDP_API_KEY_ID" not in detail
        assert "CDP_API_KEY_SECRET" in detail
        assert "CDP_WALLET_SECRET" in detail


class TestDataCoreContract:
    def test_data_core_routes_are_registered(self, client):
        paths = client.get("/openapi.json").json()["paths"]

        assert "/ingest" in paths
        assert "/sessions/{session_id}/status" in paths
        assert "/query" in paths
        assert "/redeem" in paths
        assert "/feedback" in paths
        assert "/attribution/{transaction_id}" in paths

    def test_data_core_stubs_return_501(self, client):
        seller_id = str(uuid4())
        buyer_id = str(uuid4())
        session_id = str(uuid4())
        page_id = str(uuid4())
        transaction_id = str(uuid4())

        responses = [
            client.post(
                "/ingest",
                data={"seller_id": seller_id, "original_prompt": "Research a topic"},
                files={"file": ("report.md", b"# Report", "text/markdown")},
            ),
            client.get(f"/sessions/{session_id}/status"),
            client.post("/query", json={"buyer_id": buyer_id, "query_text": "topic"}),
            client.post("/redeem", json={"transaction_id": transaction_id}),
            client.post(
                "/feedback",
                json={
                    "transaction_id": transaction_id,
                    "page_id": page_id,
                    "rating": 1,
                    "source": "explicit",
                },
            ),
            client.get(f"/attribution/{transaction_id}"),
        ]

        for response in responses:
            assert response.status_code == 501
            assert "not implemented yet" in response.json()["detail"]
