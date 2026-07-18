from fastapi import FastAPI, HTTPException

from app.api.data_core import router as data_core_router
from app.wallet import MissingCredentialsError, create_seller_account

app = FastAPI(title="CacheApp Data Core")
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
