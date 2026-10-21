import pytest

from app.catalog_service import CatalogNotFoundError, CatalogService
from app.config import Settings
from app import openmetadata_client
from app.openmetadata_client import OpenMetadataReader
from conftest import Page, entity


def test_list_services_follows_pages_and_sorts_by_name(fake_reader):
    fake_reader.add_pages(
        "DatabaseService",
        [
            Page([entity("svc-1", "warehouse", "warehouse")], after="next"),
            Page([entity("svc-2", "Analytics", "Analytics")]),
        ],
    )
    service = CatalogService(fake_reader, cache_ttl_seconds=60)

    result = service.list_services()

    assert [item.model_dump() for item in result] == [
        {"id": "svc-2", "name": "Analytics", "fullyQualifiedName": "Analytics"},
        {"id": "svc-1", "name": "warehouse", "fullyQualifiedName": "warehouse"},
    ]
    assert fake_reader.calls[0].params == {"limit": 100}
    assert fake_reader.calls[1].params == {"limit": 100, "after": "next"}


def test_list_databases_uses_parent_fqn_filter_and_follows_pages(fake_reader):
    fake_reader.add_parent("DatabaseService", "svc-1", entity("svc-1", "Warehouse", "Warehouse"))
    fake_reader.add_pages(
        "Database",
        [
            Page([entity("db-1", "Warehouse", "Warehouse.Warehouse")], after="next"),
            Page([entity("db-2", "Mart", "Warehouse.Mart")]),
        ],
        service="Warehouse",
    )
    service = CatalogService(fake_reader, cache_ttl_seconds=60)

    result = service.list_databases("svc-1")

    assert [item.id for item in result] == ["db-2", "db-1"]
    assert [item.fullyQualifiedName for item in result] == ["Warehouse.Mart", "Warehouse.Warehouse"]
    assert fake_reader.calls[0].method == "get_by_id"
    assert fake_reader.calls[1].params == {"service": "Warehouse", "limit": 100}
    assert fake_reader.calls[2].params == {"service": "Warehouse", "limit": 100, "after": "next"}


def test_list_schemas_uses_parent_fqn_filter_and_follows_pages(fake_reader):
    fake_reader.add_parent("Database", "db-1", entity("db-1", "Sales", "Warehouse.Sales"))
    fake_reader.add_pages(
        "DatabaseSchema",
        [
            Page([entity("schema-1", "zeta", "Warehouse.Sales.zeta")], after="more"),
            Page([entity("schema-2", "Alpha", "Warehouse.Sales.Alpha")]),
        ],
        database="Warehouse.Sales",
    )
    service = CatalogService(fake_reader, cache_ttl_seconds=60)

    result = service.list_schemas("db-1")

    assert [item.id for item in result] == ["schema-2", "schema-1"]
    assert fake_reader.calls[1].params == {"database": "Warehouse.Sales", "limit": 100}
    assert fake_reader.calls[2].params == {"database": "Warehouse.Sales", "limit": 100, "after": "more"}


@pytest.mark.parametrize("method,parent_type", [("list_databases", "DatabaseService"), ("list_schemas", "Database")])
def test_unknown_parent_raises_without_listing_children(fake_reader, method, parent_type):
    service = CatalogService(fake_reader, cache_ttl_seconds=60)

    with pytest.raises(CatalogNotFoundError):
        getattr(service, method)("missing")

    assert len(fake_reader.calls) == 1
    assert fake_reader.calls[0].entity.__name__ == parent_type


def test_reader_translates_pagination_arguments_for_sdk():
    class Client:
        def list_entities(self, **kwargs):
            self.kwargs = kwargs
            return "page"

        def get_by_id(self, **kwargs):
            self.get_kwargs = kwargs
            return "parent"

    client = Client()
    reader = OpenMetadataReader.__new__(OpenMetadataReader)
    reader._client = client

    assert reader.list_entities(entity=object, fields=[], params={"service": "Warehouse", "limit": 100, "after": "next"}) == "page"
    assert client.kwargs == {"entity": object, "fields": [], "params": {"service": "Warehouse"}, "limit": 100, "after": "next"}
    assert reader.get_by_id(entity=object, entity_id="svc-1", fields=[]) == "parent"
    assert client.get_kwargs == {"entity": object, "entity_id": "svc-1", "fields": []}


def test_reader_builds_openmetadata_connection_from_settings(monkeypatch):
    captured = {}

    def fake_openmetadata(connection, *, additional_client_config_arguments):
        captured["connection"] = connection
        captured["options"] = additional_client_config_arguments
        return object()

    monkeypatch.setattr(openmetadata_client, "OpenMetadata", fake_openmetadata)
    settings = Settings(
        OMD_HOST="http://localhost:8585/api",
        OMD_TOKEN="secret-token",
        OMD_REQUEST_TIMEOUT_SECONDS=12.5,
    )

    reader = OpenMetadataReader(settings)

    assert reader._client is not None
    assert captured["connection"].hostPort == "http://localhost:8585/api"
    assert captured["connection"].authProvider.value == "openmetadata"
    assert captured["connection"].securityConfig.jwtToken.get_secret_value() == "secret-token"
    assert captured["options"] == {"timeout": 12.5}
