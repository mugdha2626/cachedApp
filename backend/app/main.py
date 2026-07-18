from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from app import x402
from app.api.data_core import router as data_core_router
from app.config import Settings
from app.db import apply_migrations, close_pool, create_pool
from app.dependencies import set_data_core_service
from app.repositories.data_core import PostgresDataCoreRepository, PostgresSearchRepository
from app.services.ai import OpenAIClient
from app.services.data_core import PostgresDataCoreService, UnimplementedDataCoreService
from app.wallet import MissingCredentialsError, create_seller_account


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = Settings.from_env()
    if settings is None:
        yield
        return

    pool = await create_pool(settings.database_url)
    await apply_migrations(pool)
    set_data_core_service(
        PostgresDataCoreService(
            repository=PostgresDataCoreRepository(pool),
            search_repository=PostgresSearchRepository(pool),
            ai=OpenAIClient(settings),
            settings=settings,
        )
    )
    try:
        yield
    finally:
        set_data_core_service(UnimplementedDataCoreService())
        await close_pool(pool)


app = FastAPI(title="CacheApp Data Core", lifespan=lifespan)
app.include_router(data_core_router)


@app.get("/")
def hello() -> dict:
    return {"message": "Hello, world!"}


@app.post("/register")
async def register() -> dict:
    try:
        return await create_seller_account()
    except MissingCredentialsError as err:
        raise HTTPException(status_code=503, detail=str(err))


@app.get("/acquire-research")
async def acquire_research(request: Request) -> JSONResponse:
    """x402-gated test endpoint: pay $0.01 USDC to read the sample report."""
    resource_url = str(request.url)
    requirements = x402.payment_requirements(resource=resource_url, amount_atomic="10000")  # $0.01

    def rejected(error: str | None = None) -> JSONResponse:
        body = x402.payment_required(
            resource_url, "CacheApp deep-research sample report", requirements, error=error
        )
        return JSONResponse(status_code=402, content=body, headers={"PAYMENT-REQUIRED": x402.encode_header(body)})

    # v2 clients send PAYMENT-SIGNATURE; v1 clients send X-PAYMENT.
    header = request.headers.get("PAYMENT-SIGNATURE") or request.headers.get("X-PAYMENT")
    if not header:
        return rejected()

    try:
        payment = x402.decode_payment(header)
    except ValueError as err:
        return rejected(error=f"Invalid payment header: {err}")

    verification = await x402.verify_payment(payment, requirements)
    if not verification.get("isValid"):
        return rejected(error=verification.get("invalidReason") or "Payment verification failed")

    settlement = await x402.settle_payment(payment, requirements)
    if not settlement.get("success"):
        return rejected(error=settlement.get("errorReason") or "Payment settlement failed")

    receipt = x402.encode_header(settlement)
    return JSONResponse(
        content={
            "report": "Sample deep-research report: paid content unlocked.",
            "payer": verification.get("payer"),
        },
        headers={"PAYMENT-RESPONSE": receipt, "X-PAYMENT-RESPONSE": receipt},
    )
