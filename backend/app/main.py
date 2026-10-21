from typing import Protocol

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.catalog_service import CatalogNotFoundError, CatalogService
from app.config import get_settings
from app.models import CatalogItem, GraphResponse
from app.openmetadata_client import OpenMetadataReader


class CatalogServiceProtocol(Protocol):
    def list_services(self) -> list[CatalogItem]:
        raise NotImplementedError

    def list_databases(self, service_id: str) -> list[CatalogItem]:
        raise NotImplementedError

    def list_schemas(self, database_id: str) -> list[CatalogItem]:
        raise NotImplementedError

    def get_schema_graph(self, schema_id: str, refresh: bool = False) -> GraphResponse:
        raise NotImplementedError


def create_app(catalog_service: CatalogServiceProtocol | None = None) -> FastAPI:
    app = FastAPI(title="OpenMetadata ERD Adapter", version="0.1.0")
    service = catalog_service

    def get_catalog_service() -> CatalogServiceProtocol:
        nonlocal service
        if service is None:
            settings = get_settings()
            service = CatalogService(
                OpenMetadataReader(settings),
                cache_ttl_seconds=settings.cache_ttl_seconds,
            )
        return service

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_methods=["GET"],
        allow_headers=["Content-Type"],
    )

    @app.exception_handler(CatalogNotFoundError)
    def catalog_not_found(_request: Request, _exc: CatalogNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": "Catalog parent was not found"})

    @app.get("/api/services", response_model=list[CatalogItem])
    def list_services() -> list[CatalogItem]:
        return get_catalog_service().list_services()

    @app.get("/api/databases", response_model=list[CatalogItem])
    def list_databases(serviceId: str) -> list[CatalogItem]:
        return get_catalog_service().list_databases(serviceId)

    @app.get("/api/schemas", response_model=list[CatalogItem])
    def list_schemas(databaseId: str) -> list[CatalogItem]:
        return get_catalog_service().list_schemas(databaseId)

    @app.get("/api/schemas/{schema_id}/graph", response_model=GraphResponse, response_model_by_alias=True)
    def get_graph(schema_id: str, refresh: bool = False) -> GraphResponse:
        return get_catalog_service().get_schema_graph(schema_id, refresh=refresh)

    return app


app = create_app()
