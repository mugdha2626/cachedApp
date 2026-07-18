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


@app.get("/research")
async def research(request: Request) -> JSONResponse:
    """x402-gated test endpoint: pay $0.01 USDC to read the sample report."""
    requirements = x402.payment_requirements(
        resource=str(request.url),
        description="CacheApp deep-research sample report",
        amount_atomic="10000",  # $0.01
    )

    header = request.headers.get("X-PAYMENT")
    if not header:
        return JSONResponse(status_code=402, content=x402.payment_required(requirements))

    try:
        payment = x402.decode_payment(header)
    except ValueError as err:
        return JSONResponse(
            status_code=402,
            content=x402.payment_required(requirements, error=f"Invalid X-PAYMENT header: {err}"),
        )

    verification = await x402.verify_payment(payment, requirements)
    if not verification.get("isValid"):
        error = verification.get("invalidReason") or "Payment verification failed"
        return JSONResponse(status_code=402, content=x402.payment_required(requirements, error=error))

    settlement = await x402.settle_payment(payment, requirements)
    if not settlement.get("success"):
        error = settlement.get("errorReason") or "Payment settlement failed"
        return JSONResponse(status_code=402, content=x402.payment_required(requirements, error=error))

    return JSONResponse(
        content={
            "report": "Sample deep-research report: paid content unlocked.",
            "payer": verification.get("payer"),
        },
        headers={"X-PAYMENT-RESPONSE": x402.encode_settlement(settlement)},
    )
