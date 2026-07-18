"""Server side of the x402 v2 payment protocol ("exact" scheme, Base Sepolia).

A gated endpoint answers 402 with payment requirements (PAYMENT-REQUIRED
header + JSON body) until the client retries with a PAYMENT-SIGNATURE
header (v1 X-PAYMENT is also accepted), which we verify and settle through
an x402 facilitator. The protocol shapes are small, so they live here
explicitly rather than behind an SDK.
"""

import base64
import binascii
import json
import os
from typing import Any

import httpx

X402_VERSION = 2
SCHEME = "exact"
NETWORK = "eip155:84532"  # Base Sepolia (CAIP-2, required by x402 v2)
USDC_ADDRESS = "0x036CbD53842c5426634e7929541eC2318f3dCF7e"
FACILITATOR_URL = os.environ.get("X402_FACILITATOR_URL", "https://x402.org/facilitator")

# The registered seller's wallet (the address /register returns).
SELLER_ADDRESS = "0x9eFAe17D9525f797E26A7121aAb73d60DBF6706E"


def get_payment_address(resource: str) -> str:
    """Resolve which address gets paid for `resource`.

    Every resource currently pays the single hardcoded seller wallet. When
    CacheApp has many sellers, this is the one place to swap in a real
    lookup (resource -> seller address).
    """
    return SELLER_ADDRESS


def payment_requirements(resource: str, amount_atomic: str) -> dict:
    """Build one v2 PaymentRequirements entry.

    `amount_atomic` is in USDC atomic units (6 decimals): "10000" = $0.01.
    `extra` carries the EIP-712 domain of the asset for EIP-3009 signing.
    """
    return {
        "scheme": SCHEME,
        "network": NETWORK,
        "amount": amount_atomic,
        "asset": USDC_ADDRESS,
        "payTo": get_payment_address(resource),
        "maxTimeoutSeconds": 60,
        "extra": {"name": "USDC", "version": "2"},
    }


def payment_required(resource_url: str, description: str, requirements: dict, error: str | None = None) -> dict:
    """Body of a 402 response (v2 PaymentRequired)."""
    body: dict[str, Any] = {
        "x402Version": X402_VERSION,
        "resource": {
            "url": resource_url,
            "description": description,
            "mimeType": "application/json",
        },
        "accepts": [requirements],
    }
    if error is not None:
        body["error"] = error
    return body


def encode_header(payload: dict) -> str:
    """Base64-encode a protocol object for an HTTP header."""
    return base64.b64encode(json.dumps(payload).encode()).decode()


def decode_payment(header: str) -> dict:
    """Decode a client's payment header (base64-encoded JSON payload)."""
    try:
        payload = json.loads(base64.b64decode(header, validate=True))
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError) as err:
        raise ValueError(f"not base64-encoded JSON: {err}") from err
    if not isinstance(payload, dict):
        raise ValueError("payment payload must be a JSON object")
    return payload


async def _facilitator_post(path: str, payment: dict, requirements: dict) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{FACILITATOR_URL}{path}",
            json={
                "x402Version": payment.get("x402Version", X402_VERSION),
                "paymentPayload": payment,
                "paymentRequirements": requirements,
            },
        )
        response.raise_for_status()
        return response.json()


async def verify_payment(payment: dict, requirements: dict) -> dict:
    """Ask the facilitator whether the signed payment is valid.

    Returns e.g. {"isValid": bool, "invalidReason": str | None, "payer": "0x.."}.
    """
    return await _facilitator_post("/verify", payment, requirements)


async def settle_payment(payment: dict, requirements: dict) -> dict:
    """Execute the payment on-chain through the facilitator.

    Returns e.g. {"success": bool, "errorReason": str | None, "transaction": "0x.."}.
    """
    return await _facilitator_post("/settle", payment, requirements)
