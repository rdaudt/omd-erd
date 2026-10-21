from dataclasses import dataclass
from pathlib import Path
from time import monotonic

from metadata.generated.schema.entity.data.database import Database
from metadata.generated.schema.entity.data.databaseSchema import DatabaseSchema
from metadata.generated.schema.entity.data.table import Table
from metadata.generated.schema.entity.services.databaseService import DatabaseService
from metadata.ingestion.ometa.client import APIError, HtmlResponseError, RestTransportError, RetryException
from metadata.ingestion.ometa.utils import model_str
from requests.exceptions import ConnectionError as RequestsConnectionError, Timeout as RequestsTimeout

from app.models import CatalogItem, ColumnModel, GraphResponse, RelationshipModel, TableModel
from app.openmetadata_client import OpenMetadataReader


class CatalogNotFoundError(Exception):
    pass


@dataclass
class _CacheEntry:
    expires_at: float
    graph: GraphResponse


def _text(value: object | None) -> str | None:
    if value is None:
        return None
    unwrapped = getattr(value, "root", value)
    return str(getattr(unwrapped, "value", unwrapped))


def _column_flags(table) -> tuple[set[str], set[str]]:
    primary_keys: set[str] = set()
    foreign_keys: set[str] = set()
    for constraint in table.tableConstraints or []:
        names = {_text(name) for name in constraint.columns or []}
        names.discard(None)
        constraint_type = _text(constraint.constraintType)
        if constraint_type == "PRIMARY_KEY":
            primary_keys.update(names)
        elif constraint_type == "FOREIGN_KEY":
            foreign_keys.update(names)
    return primary_keys, foreign_keys


def _map_column(column, primary_keys: set[str], foreign_keys: set[str]) -> ColumnModel:
    name = _text(column.name) or ""
    constraint = _text(getattr(column, "constraint", None))
    is_primary_key = name in primary_keys or constraint == "PRIMARY_KEY"
    return ColumnModel(
        name=name,
        dataType=_text(column.dataType) or "UNKNOWN",
        nullable=not is_primary_key and constraint != "NOT_NULL",
        primaryKey=is_primary_key,
        foreignKey=name in foreign_keys,
        description=_text(getattr(column, "description", None)),
    )


def _display_owner(table) -> str | None:
    owners = getattr(table, "owners", None)
    owners = getattr(owners, "root", owners) or []
    if not owners:
        return None
    return _text(getattr(owners[0], "displayName", None) or getattr(owners[0], "name", None))


def _display_tags(table) -> tuple[list[str], str | None]:
    labels = sorted(filter(None, (_text(tag.tagFQN) for tag in (table.tags or []))))
    tier = next((label for label in labels if label.startswith("Tier.")), None)
    return [label for label in labels if label != tier], tier.removeprefix("Tier.") if tier else None


def _map_relationships(tables: list[object], warnings: list[str]) -> list[RelationshipModel]:
    by_fqn = {_text(table.fullyQualifiedName): table for table in tables}
    ordered_fqns = sorted((fqn for fqn in by_fqn if fqn), key=len, reverse=True)
    relationships: list[RelationshipModel] = []
    for table in tables:
        source_columns = {_text(column.name) for column in table.columns or []}
        for constraint in table.tableConstraints or []:
            if _text(constraint.constraintType) != "FOREIGN_KEY":
                continue
            local = [_text(name) for name in constraint.columns or []]
            referred = [_text(name) for name in constraint.referredColumns or []]
            if not local or len(local) != len(referred):
                warnings.append(f"Invalid foreign key on {_text(table.name)}: local and referred columns do not match")
                continue
            for source_column, reference in zip(local, referred):
                target_fqn = next((fqn for fqn in ordered_fqns if reference and reference.startswith(fqn + ".")), None)
                target_table = by_fqn[target_fqn] if target_fqn else None
                target_column = reference[len(target_fqn) + 1:].rsplit(".", 1)[-1] if target_fqn else None
                target_columns = {_text(column.name) for column in target_table.columns or []} if target_table else set()
                if not source_column or source_column not in source_columns or not target_table or not target_column or target_column not in target_columns:
                    warnings.append(f"Unresolved foreign key on {_text(table.name)}: {source_column} -> {reference}")
                    continue
                source_id = _text(table.id) or ""
                target_id = _text(target_table.id) or ""
                relationships.append(RelationshipModel(
                    id=f"{source_id}.{source_column}->{target_id}.{target_column}",
                    sourceTableId=source_id,
                    sourceColumn=source_column,
                    targetTableId=target_id,
                    targetColumn=target_column,
                ))
    return sorted(relationships, key=lambda relationship: relationship.id)


class CatalogService:
    def __init__(self, reader: OpenMetadataReader, cache_ttl_seconds: int):
        self._reader = reader
        self._cache_ttl_seconds = cache_ttl_seconds
        self._graph_cache: dict[str, _CacheEntry] = {}

    def _all_entities(self, entity, *, fields: list[str], params: dict[str, str]) -> list[object]:
        items: list[object] = []
        after: str | None = None
        while True:
            page_params: dict[str, str | int] = {**params, "limit": 100}
            if after:
                page_params["after"] = after
            page = self._reader.list_entities(entity=entity, fields=fields, params=page_params)
            items.extend(page.entities)
            after = page.after
            if not after:
                return items

    @staticmethod
    def _catalog_items(entities: list[object]) -> list[CatalogItem]:
        items = [
            CatalogItem(
                id=model_str(entity.id),
                name=model_str(entity.name),
                fullyQualifiedName=model_str(entity.fullyQualifiedName),
            )
            for entity in entities
        ]
        return sorted(items, key=lambda item: item.name.casefold())

    def list_services(self) -> list[CatalogItem]:
        return self._catalog_items(self._all_entities(DatabaseService, fields=[], params={}))

    def list_databases(self, service_id: str) -> list[CatalogItem]:
        parent = self._reader.get_by_id(entity=DatabaseService, entity_id=service_id, fields=[])
        if parent is None:
            raise CatalogNotFoundError(service_id)
        entities = self._all_entities(
            Database,
            fields=[],
            params={"service": model_str(parent.fullyQualifiedName)},
        )
        return self._catalog_items(entities)

    def list_schemas(self, database_id: str) -> list[CatalogItem]:
        parent = self._reader.get_by_id(entity=Database, entity_id=database_id, fields=[])
        if parent is None:
            raise CatalogNotFoundError(database_id)
        entities = self._all_entities(
            DatabaseSchema,
            fields=[],
            params={"database": model_str(parent.fullyQualifiedName)},
        )
        return self._catalog_items(entities)

    def get_schema_graph(self, schema_id: str, refresh: bool = False) -> GraphResponse:
        now = monotonic()
        cached = self._graph_cache.get(schema_id)
        if not refresh and cached and cached.expires_at > now:
            return cached.graph

        try:
            schema = self._reader.get_by_id(entity=DatabaseSchema, entity_id=schema_id, fields=[])
            if schema is None:
                raise CatalogNotFoundError(schema_id)
            tables = self._all_entities(
                Table,
                fields=["columns", "tableConstraints", "owners", "tags"],
                params={"databaseSchema": model_str(schema.fullyQualifiedName)},
            )
        except (RequestsConnectionError, RequestsTimeout, TimeoutError, ConnectionError,
                RestTransportError, RetryException, HtmlResponseError, APIError):
            return GraphResponse.model_validate_json(Path(__file__).with_name("sample_graph.json").read_text(encoding="utf-8"))

        warnings: list[str] = []
        mapped_tables: list[TableModel] = []
        for table in tables:
            primary_keys, foreign_keys = _column_flags(table)
            tags, tier = _display_tags(table)
            mapped_tables.append(TableModel(
                id=_text(table.id) or "",
                name=_text(table.name) or "",
                fullyQualifiedName=_text(table.fullyQualifiedName) or "",
                description=_text(getattr(table, "description", None)),
                owner=_display_owner(table),
                tags=tags,
                tier=tier,
                columns=[_map_column(column, primary_keys, foreign_keys) for column in table.columns or []],
            ))
        graph = GraphResponse(
            source="live",
            schema=CatalogItem(id=_text(schema.id) or "", name=_text(schema.name) or "", fullyQualifiedName=_text(schema.fullyQualifiedName) or ""),
            tables=sorted(mapped_tables, key=lambda table: (table.name.casefold(), table.id)),
            relationships=_map_relationships(tables, warnings),
            warnings=warnings,
        )
        if self._cache_ttl_seconds > 0:
            self._graph_cache[schema_id] = _CacheEntry(now + self._cache_ttl_seconds, graph)
        return graph
