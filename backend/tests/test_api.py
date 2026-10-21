from fastapi.testclient import TestClient

from app.main import create_app


class StubCatalogService:
    def list_services(self):
        return [{"id": "svc-1", "name": "MSSQL Desktop", "fullyQualifiedName": "MSSQL Desktop"}]


def test_services_contract_is_read_only():
    client = TestClient(create_app(StubCatalogService()))

    response = client.get("/api/services")

    assert response.status_code == 200
    assert response.json() == [
        {"id": "svc-1", "name": "MSSQL Desktop", "fullyQualifiedName": "MSSQL Desktop"}
    ]
    assert client.post("/api/services").status_code == 405
