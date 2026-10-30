from functools import lru_cache

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.omd import OmdClient, OmdError

app = FastAPI(title="Data Marketplace demo")


@lru_cache
def get_omd() -> OmdClient:
    return OmdClient(get_settings())


@app.exception_handler(OmdError)
async def omd_error_handler(request: Request, exc: OmdError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": exc.message})


@app.get("/api/health")
def health(omd: OmdClient = Depends(get_omd)) -> dict:
    try:
        omd.get("/system/version")
        state = "up"
    except OmdError:
        state = "down"
    return {"status": "ok", "omd": state}
