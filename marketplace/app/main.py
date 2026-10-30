from functools import lru_cache
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator

from app.catalog import CatalogService
from app.config import get_settings
from app.omd import OmdClient, OmdError
from app.requests_store import AccessRequest, AccessRequestStore
from app.shaping import facets, filter_products

app = FastAPI(title="Data Marketplace demo")


@lru_cache
def get_omd() -> OmdClient:
    return OmdClient(get_settings())


@lru_cache
def get_catalog() -> CatalogService:
    return CatalogService(get_omd(), get_settings().cache_ttl_seconds)


@lru_cache
def get_store() -> AccessRequestStore:
    return AccessRequestStore()


class AccessRequestIn(BaseModel):
    product: str
    justification: str
    duration: str

    @field_validator("justification", "duration")
    @classmethod
    def not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


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


@app.get("/api/products")
def list_products(
    domain: str | None = None, sensitivity: str | None = None, quality: str | None = None,
    owner: str | None = None, certification: str | None = None, q: str | None = None,
    catalog: CatalogService = Depends(get_catalog),
) -> dict:
    everything = catalog.list_products()
    items = filter_products(
        everything, domain=domain, sensitivity=sensitivity, quality=quality,
        owner=owner, certification=certification, q=q,
    )
    return {"items": items, "facets": facets(everything)}


@app.get("/api/products/{name}")
def get_product(name: str, catalog: CatalogService = Depends(get_catalog)):
    detail = catalog.get_product(name)
    if detail is None:
        raise HTTPException(404, "Data product not found")
    return detail


@app.post("/api/access-requests")
def create_access_request(
    body: AccessRequestIn, catalog: CatalogService = Depends(get_catalog),
    store: AccessRequestStore = Depends(get_store),
) -> AccessRequest:
    product = next((p for p in catalog.list_products() if p.name == body.product), None)
    if product is None:
        raise HTTPException(404, "Data product not found")
    if not product.entra_group:
        raise HTTPException(409, "This data product has no Entra group mapped, so access cannot be requested")
    return store.create(product.name, product.display_name, body.justification, body.duration, product.entra_group)


@app.get("/api/access-requests/{number}")
def get_access_request(number: str, store: AccessRequestStore = Depends(get_store)) -> AccessRequest:
    request = store.get(number)
    if request is None:
        raise HTTPException(404, "Request not found")
    return request


# Static frontend last, so it never shadows the /api routes.
app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="static")
