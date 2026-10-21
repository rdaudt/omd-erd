from typing import Protocol

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.models import CatalogItem


class CatalogServiceProtocol(Protocol):
    def list_services(self) -> list[CatalogItem]:
        raise NotImplementedError


def create_app(catalog_service: CatalogServiceProtocol | None = None) -> FastAPI:
    app = FastAPI(title="OpenMetadata ERD Adapter", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_methods=["GET"],
        allow_headers=["Content-Type"],
    )

    @app.get("/api/services", response_model=list[CatalogItem])
    def list_services() -> list[CatalogItem]:
        if catalog_service is None:
            raise RuntimeError("Catalog service is not configured")
        return catalog_service.list_services()

    return app


app = create_app()
