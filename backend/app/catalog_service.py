from metadata.generated.schema.entity.data.database import Database
from metadata.generated.schema.entity.data.databaseSchema import DatabaseSchema
from metadata.generated.schema.entity.services.databaseService import DatabaseService
from metadata.ingestion.ometa.utils import model_str

from app.models import CatalogItem
from app.openmetadata_client import OpenMetadataReader


class CatalogNotFoundError(Exception):
    pass


class CatalogService:
    def __init__(self, reader: OpenMetadataReader, cache_ttl_seconds: int):
        self._reader = reader
        self._cache_ttl_seconds = cache_ttl_seconds

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
