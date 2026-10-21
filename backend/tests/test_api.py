from fastapi.testclient import TestClient
from types import SimpleNamespace

from app.catalog_service import CatalogNotFoundError
import app.main as main
from app.main import create_app


class StubCatalogService:
    def list_services(self):
        return [{"id": "svc-1", "name": "MSSQL Desktop", "fullyQualifiedName": "MSSQL Desktop"}]

    def list_databases(self, service_id: str):
        if service_id != "svc-1":
            raise CatalogNotFoundError(service_id)
        return [{"id": "db-1", "name": "Warehouse", "fullyQualifiedName": "MSSQL Desktop.Warehouse"}]

    def list_schemas(self, database_id: str):
        if database_id != "db-1":
            raise CatalogNotFoundError(database_id)
        return [{"id": "schema-1", "name": "dbo", "fullyQualifiedName": "MSSQL Desktop.Warehouse.dbo"}]


def test_services_contract_is_read_only():
    client = TestClient(create_app(StubCatalogService()))

    response = client.get("/api/services")

    assert response.status_code == 200
    assert response.json() == [
        {"id": "svc-1", "name": "MSSQL Desktop", "fullyQualifiedName": "MSSQL Desktop"}
    ]
    assert client.post("/api/services").status_code == 405


def test_hierarchy_routes_return_catalog_items():
    client = TestClient(create_app(StubCatalogService()))

    assert client.get("/api/databases", params={"serviceId": "svc-1"}).json() == [
        {"id": "db-1", "name": "Warehouse", "fullyQualifiedName": "MSSQL Desktop.Warehouse"}
    ]
    assert client.get("/api/schemas", params={"databaseId": "db-1"}).json() == [
        {"id": "schema-1", "name": "dbo", "fullyQualifiedName": "MSSQL Desktop.Warehouse.dbo"}
    ]


def test_hierarchy_routes_require_parent_query_parameters():
    client = TestClient(create_app(StubCatalogService()))

    assert client.get("/api/databases").status_code == 422
    assert client.get("/api/schemas").status_code == 422


def test_unknown_parent_returns_404_without_exposing_identifier():
    client = TestClient(create_app(StubCatalogService()))

    for path, params in [
        ("/api/databases", {"serviceId": "missing"}),
        ("/api/schemas", {"databaseId": "missing"}),
    ]:
        response = client.get(path, params=params)
        assert response.status_code == 404
        assert response.json() == {"detail": "Catalog parent was not found"}


def test_default_app_lazily_constructs_one_catalog_service(monkeypatch):
    constructions = []
    settings = SimpleNamespace(cache_ttl_seconds=60)
    reader = object()
    monkeypatch.setattr(main, "get_settings", lambda: settings, raising=False)
    monkeypatch.setattr(main, "OpenMetadataReader", lambda value: reader, raising=False)

    def build_service(value, *, cache_ttl_seconds):
        constructions.append((value, cache_ttl_seconds))
        return StubCatalogService()

    monkeypatch.setattr(main, "CatalogService", build_service, raising=False)
    client = TestClient(create_app())

    assert constructions == []
    assert client.get("/api/services").status_code == 200
    assert client.get("/api/databases", params={"serviceId": "svc-1"}).status_code == 200
    assert constructions == [(reader, 60)]
