from fastapi.testclient import TestClient
from types import SimpleNamespace

from app.catalog_service import CatalogNotFoundError
import app.main as main
from app.main import create_app
from app.config import Settings
from app import openmetadata_client
from metadata.ingestion.ometa.client import RestTransportError


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

    def get_schema_graph(self, schema_id: str, refresh: bool = False):
        self.graph_request = (schema_id, refresh)
        return {
            "source": "sample",
            "schema": {"id": schema_id, "name": "dbo", "fullyQualifiedName": "MSSQL Desktop.Warehouse.dbo"},
            "tables": [],
            "relationships": [],
            "notices": ["2 cross-schema relationships are not shown."],
            "warnings": ["OpenMetadata is unavailable; showing bundled sample data."],
        }


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

def test_parent_ids_reject_path_delimiters_before_catalog_access():
    client = TestClient(create_app(StubCatalogService()))

    response = client.get("/api/databases", params={"serviceId": "../../system/version"})

    assert response.status_code == 422


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


def test_graph_route_serializes_schema_alias_and_forwards_refresh():
    service = StubCatalogService()
    client = TestClient(create_app(service))

    response = client.get("/api/schemas/schema-1/graph", params={"refresh": "true"})

    assert response.status_code == 200
    assert response.json()["schema"]["id"] == "schema-1"
    assert "schema_" not in response.json()
    assert response.json()["warnings"]
    assert response.json()["notices"] == ["2 cross-schema relationships are not shown."]
    assert service.graph_request == ("schema-1", True)

def test_graph_route_rejects_unsafe_schema_ids_before_service_access():
    service = StubCatalogService()
    client = TestClient(create_app(service))

    for schema_id in ["bad id", r"bad\id", "x" * 129]:
        response = client.get(f"/api/schemas/{schema_id}/graph")
        assert response.status_code == 422

    assert not hasattr(service, "graph_request")


def test_all_catalog_routes_reject_post():
    client = TestClient(create_app(StubCatalogService()))

    for path in ["/api/services", "/api/databases", "/api/schemas", "/api/schemas/schema-1/graph"]:
        assert client.post(path).status_code == 405


def test_first_graph_request_falls_back_when_sdk_version_probe_is_unavailable(monkeypatch):
    attempts = []

    def unavailable_sdk(*args, **kwargs):
        attempts.append(True)
        raise RestTransportError('GET', 'http://localhost:8585/api/v1/system/version', ConnectionError('offline'))

    monkeypatch.setattr(openmetadata_client, 'OpenMetadata', unavailable_sdk)
    monkeypatch.setattr(main, 'get_settings', lambda: Settings(OMD_HOST='http://localhost:8585/api', OMD_TOKEN='test-token'))
    client = TestClient(create_app(), raise_server_exceptions=False)

    for _ in range(2):
        response = client.get('/api/schemas/known-schema/graph')
        assert response.status_code == 200
        assert response.json()['source'] == 'sample'
        assert response.json()['tables']
        assert {table['entityType'] for table in response.json()['tables']} == {'table', 'view'}
        assert response.json()['warnings']
    assert len(attempts) == 2  # Failed initialization is retried, not cached forever.
