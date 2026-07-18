"""CDP wallet logic. All CDP credentials and account management live here —
clients (like the CLI) only ever see the resulting wallet address."""

import os

from cdp import CdpClient

ACCOUNT_NAME = "x402-seller"
NETWORK = "eip155:84532"  # Base Sepolia (CAIP-2)
REQUIRED_ENV = ["CDP_API_KEY_ID", "CDP_API_KEY_SECRET", "CDP_WALLET_SECRET"]


class MissingCredentialsError(RuntimeError):
    pass


async def create_seller_account() -> dict:
    """Get or create the seller's CDP-managed wallet and request testnet USDC.

    Idempotent: repeated calls return the same account. The faucet request is
    best-effort — a failure there never fails registration.
    """
    missing = [key for key in REQUIRED_ENV if not os.environ.get(key)]
    if missing:
        raise MissingCredentialsError(
            f"Missing CDP credentials: {', '.join(missing)}. "
            "Set them in the backend environment (see .env.example)."
        )

    async with CdpClient() as cdp:
        account = await cdp.evm.get_or_create_account(name=ACCOUNT_NAME)

        faucet_tx = None
        try:
            faucet_tx = await cdp.evm.request_faucet(
                address=account.address, network="base-sepolia", token="usdc"
            )
        except Exception:
            pass

    return {
        "name": ACCOUNT_NAME,
        "address": account.address,
        "network": NETWORK,
        "faucet_tx": faucet_tx,
    }
