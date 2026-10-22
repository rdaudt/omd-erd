import pytest
from requests.exceptions import ConnectionError as RequestsConnectionError
from metadata.generated.schema.entity.data.table import Column, Constraint, ConstraintType, DataType, TableConstraint

from app.catalog_service import CatalogNotFoundError, CatalogService
from app.config import Settings
from app import openmetadata_client
from app.openmetadata_client import OpenMetadataReader
from conftest import Page, entity
from types import SimpleNamespace


def graph_column(name: str, data_type=DataType.INT):
    return SimpleNamespace(
        name=SimpleNamespace(root=name),
        dataType=data_type,
        constraint=None,
        description=None,
    )


def graph_table(table_id: str, name: str, fqn: str, columns, constraints=None, *, owners=None, tags=None):
    table = entity(table_id, name, fqn)
    table.columns = columns
    table.tableConstraints = constraints
    table.description = None
    table.owners = SimpleNamespace(root=owners or [])
    table.tags = tags or []
    return table


def add_graph_schema(fake_reader, tables):
    fake_reader.add_parent("DatabaseSchema", "schema-1", entity("schema-1", "dbo", "svc.db.dbo"))
    fake_reader.add_pages("Table", [Page(tables)], databaseSchema="svc.db.dbo")


def test_graph_normalizes_sdk_shaped_tables_and_foreign_keys(fake_reader):
    customer = graph_table(
        "customer", "customer", "svc.db.dbo.customer", [graph_column("id")],
        [TableConstraint(constraintType=ConstraintType.PRIMARY_KEY, columns=["id"])],
        owners=[SimpleNamespace(displayName="Data Architecture", name="data_arch")],
        tags=[SimpleNamespace(tagFQN=SimpleNamespace(root="Tier.Tier1")), SimpleNamespace(tagFQN=SimpleNamespace(root="PII.Sensitive"))],
    )
    orders = graph_table(
        "orders", "orders", "svc.db.dbo.orders", [graph_column("id"), graph_column("customer_id")],
        [TableConstraint(
            constraintType=ConstraintType.FOREIGN_KEY,
            columns=["customer_id"],
            referredColumns=["svc.db.dbo.customer.id"],
        )],
    )
    add_graph_schema(fake_reader, [orders, customer])
    service = CatalogService(fake_reader, cache_ttl_seconds=60)

    graph = service.get_schema_graph("schema-1")

    assert graph.source == "live"
    assert [table.name for table in graph.tables] == ["customer", "orders"]
    assert graph.tables[0].owner == "Data Architecture"
    assert graph.tables[0].tier == "Tier1"
    assert graph.tables[0].tags == ["PII.Sensitive"]
    assert graph.tables[0].columns[0].primaryKey is True
    assert graph.tables[0].columns[0].dataType == "INT"
    assert graph.tables[1].columns[1].foreignKey is True
    assert graph.relationships[0].model_dump() == {
        "id": "orders.customer_id->customer.id",
        "sourceTableId": "orders",
        "sourceColumn": "customer_id",
        "targetTableId": "customer",
        "targetColumn": "id",
    }
    assert graph.warnings == []
    assert fake_reader.calls[0].fields == []
    assert fake_reader.calls[1].fields == ["columns", "tableConstraints", "owners", "tags"]
    assert fake_reader.calls[1].params == {"databaseSchema": "svc.db.dbo", "limit": 100}


@pytest.mark.parametrize(
    "constraint,expected_nullable,expected_primary",
    [
        (Constraint.NULL, True, False),
        (Constraint.NOT_NULL, False, False),
        (Constraint.PRIMARY_KEY, False, True),
        (None, True, False),
    ],
)
def test_graph_maps_generated_column_constraint(fake_reader, constraint, expected_nullable, expected_primary):
    column = Column(name="id", dataType=DataType.INT, constraint=constraint)
    assert not hasattr(column, "nullable")
    add_graph_schema(fake_reader, [graph_table("customer", "customer", "svc.db.dbo.customer", [column])])

    graph = CatalogService(fake_reader, cache_ttl_seconds=60).get_schema_graph("schema-1")

    mapped = graph.tables[0].columns[0]
    assert mapped.nullable is expected_nullable
    assert mapped.primaryKey is expected_primary


def test_graph_table_primary_key_constraint_marks_generated_column_non_nullable(fake_reader):
    column = Column(name="id", dataType=DataType.INT)
    table = graph_table(
        "customer", "customer", "svc.db.dbo.customer", [column],
        [TableConstraint(constraintType=ConstraintType.PRIMARY_KEY, columns=["id"])],
    )
    add_graph_schema(fake_reader, [table])

    mapped = CatalogService(fake_reader, cache_ttl_seconds=60).get_schema_graph("schema-1").tables[0].columns[0]

    assert mapped.primaryKey is True
    assert mapped.nullable is False


def test_graph_skips_malformed_constraints_with_warning(fake_reader):
    orders = graph_table(
        "orders", "orders", "svc.db.dbo.orders", [graph_column("id"), graph_column("customer_id")],
        [TableConstraint(constraintType=ConstraintType.FOREIGN_KEY, columns=["customer_id"], referredColumns=["missing.table.id"])],
    )
    add_graph_schema(fake_reader, [orders])

    graph = CatalogService(fake_reader, cache_ttl_seconds=60).get_schema_graph("schema-1")

    assert graph.relationships == []
    assert graph.warnings
    assert "missing.table.id" in graph.warnings[0]


def test_graph_skips_incomplete_foreign_key_pairs(fake_reader):
    orders = graph_table(
        "orders", "orders", "svc.db.dbo.orders", [graph_column("customer_id")],
        [TableConstraint(constraintType=ConstraintType.FOREIGN_KEY, columns=["customer_id"], referredColumns=[])],
    )
    add_graph_schema(fake_reader, [orders])

    graph = CatalogService(fake_reader, cache_ttl_seconds=60).get_schema_graph("schema-1")

    assert graph.relationships == []
    assert len(graph.warnings) == 1
    assert "do not match" in graph.warnings[0]


def test_graph_skips_missing_local_or_target_columns(fake_reader):
    customer = graph_table("customer", "customer", "svc.db.dbo.customer", [graph_column("id")])
    orders = graph_table(
        "orders", "orders", "svc.db.dbo.orders", [graph_column("id")],
        [TableConstraint(
            constraintType=ConstraintType.FOREIGN_KEY,
            columns=["absent", "id"],
            referredColumns=["svc.db.dbo.customer.id", "svc.db.dbo.customer.absent"],
        )],
    )
    add_graph_schema(fake_reader, [orders, customer])

    graph = CatalogService(fake_reader, cache_ttl_seconds=60).get_schema_graph("schema-1")

    assert graph.relationships == []
    assert len(graph.warnings) == 2


def test_graph_resolves_longest_qualified_table_prefix(fake_reader):
    customer = graph_table("customer", "customer", "svc.db.dbo.customer", [graph_column("id")])
    customer_region = graph_table("customer_region", "customer.region", "svc.db.dbo.customer.region", [graph_column("id")])
    orders = graph_table(
        "orders", "orders", "svc.db.dbo.orders", [graph_column("region_id")],
        [TableConstraint(
            constraintType=ConstraintType.FOREIGN_KEY,
            columns=["region_id"],
            referredColumns=["svc.db.dbo.customer.region.id"],
        )],
    )
    add_graph_schema(fake_reader, [orders, customer, customer_region])

    graph = CatalogService(fake_reader, cache_ttl_seconds=60).get_schema_graph("schema-1")

    assert len(graph.relationships) == 1
    assert graph.relationships[0].targetTableId == "customer_region"
    assert graph.warnings == []

def test_graph_resolves_quoted_dotted_column_and_preserves_backslashes(fake_reader):
    dotted_column = "customer.id"
    backslash_column = r"path\\name"
    customer = graph_table(
        "customer", "customer", "svc.db.dbo.customer",
        [graph_column(dotted_column), graph_column(backslash_column), graph_column("id")],
    )
    orders = graph_table(
        "orders", "orders", "svc.db.dbo.orders", [graph_column("dotted_fk"), graph_column("path_fk"), graph_column("nested_fk")],
        [TableConstraint(
            constraintType=ConstraintType.FOREIGN_KEY,
            columns=["dotted_fk", "path_fk", "nested_fk"],
            referredColumns=[
                'svc.db.dbo.customer."customer.id"',
                r"svc.db.dbo.customer.path\\name",
                "svc.db.dbo.customer.region.id",
            ],
        )],
    )
    add_graph_schema(fake_reader, [orders, customer])

    graph = CatalogService(fake_reader, cache_ttl_seconds=60).get_schema_graph("schema-1")

    assert [(edge.sourceColumn, edge.targetColumn) for edge in graph.relationships] == [
        ("dotted_fk", dotted_column),
        ("path_fk", backslash_column),
    ]
    assert len(graph.warnings) == 1
    assert "nested_fk" in graph.warnings[0]


def test_graph_empty_schema_is_live_and_empty(fake_reader):
    add_graph_schema(fake_reader, [])

    graph = CatalogService(fake_reader, cache_ttl_seconds=60).get_schema_graph("schema-1")

    assert graph.source == "live"
    assert graph.tables == []
    assert graph.relationships == []
    assert graph.warnings == []


def test_graph_cache_reuses_live_result_and_refresh_bypasses_it(fake_reader):
    add_graph_schema(fake_reader, [graph_table("customer", "customer", "svc.db.dbo.customer", [graph_column("id")])])
    service = CatalogService(fake_reader, cache_ttl_seconds=60)

    first = service.get_schema_graph("schema-1")
    cached = service.get_schema_graph("schema-1")
    refreshed = service.get_schema_graph("schema-1", refresh=True)

    assert cached is first
    assert refreshed is not first
    assert [call.method for call in fake_reader.calls] == ["get_by_id", "list_entities", "get_by_id", "list_entities"]


def test_graph_cache_expires(fake_reader, monkeypatch):
    add_graph_schema(fake_reader, [])
    clock = iter([100.0, 105.0, 111.0])
    monkeypatch.setattr("app.catalog_service.monotonic", lambda: next(clock))
    service = CatalogService(fake_reader, cache_ttl_seconds=10)

    first = service.get_schema_graph("schema-1")
    assert service.get_schema_graph("schema-1") is first
    assert service.get_schema_graph("schema-1") is not first


def test_graph_connectivity_failure_uses_sample_without_caching(fake_reader, monkeypatch):
    add_graph_schema(fake_reader, [])
    original = fake_reader.get_by_id
    attempts = 0

    def failing_once(**kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RequestsConnectionError("connection refused")
        return original(**kwargs)

    monkeypatch.setattr(fake_reader, "get_by_id", failing_once)
    service = CatalogService(fake_reader, cache_ttl_seconds=60)

    sample = service.get_schema_graph("schema-1")
    live = service.get_schema_graph("schema-1")

    assert sample.source == "sample"
    assert len(sample.tables) >= 4
    assert sample.relationships
    assert sample.warnings
    assert live.source == "live"


def test_graph_programming_error_propagates(fake_reader, monkeypatch):
    add_graph_schema(fake_reader, [])
    monkeypatch.setattr(fake_reader, "get_by_id", lambda **kwargs: (_ for _ in ()).throw(ValueError("bad normalization")))

    with pytest.raises(ValueError, match="bad normalization"):
        CatalogService(fake_reader, cache_ttl_seconds=60).get_schema_graph("schema-1")


def test_graph_unknown_schema_raises_not_found(fake_reader):
    with pytest.raises(CatalogNotFoundError):
        CatalogService(fake_reader, cache_ttl_seconds=60).get_schema_graph("missing")

    assert len(fake_reader.calls) == 1


def test_graph_table_listing_failure_uses_sample(fake_reader, monkeypatch):
    add_graph_schema(fake_reader, [])
    monkeypatch.setattr(fake_reader, "list_entities", lambda **kwargs: (_ for _ in ()).throw(RequestsConnectionError("offline")))

    graph = CatalogService(fake_reader, cache_ttl_seconds=60).get_schema_graph("schema-1")

    assert graph.source == "sample"
    assert graph.warnings


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
