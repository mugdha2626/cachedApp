from fastapi import FastAPI, HTTPException

from app.wallet import MissingCredentialsError, create_seller_account

app = FastAPI(title="cachedApp backend")


@app.get("/")
def hello() -> dict:
    return {"message": "Hello, world!"}


@app.post("/register")
async def register() -> dict:
    try:
        return await create_seller_account()
    except MissingCredentialsError as err:
        raise HTTPException(status_code=503, detail=str(err))
