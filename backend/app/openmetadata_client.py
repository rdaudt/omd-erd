from metadata.generated.schema.entity.services.connections.metadata.openMetadataConnection import (
    AuthProvider,
    OpenMetadataConnection,
)
from metadata.generated.schema.security.client.openMetadataJWTClientConfig import (
    OpenMetadataJWTClientConfig,
)
from metadata.ingestion.ometa.ometa_api import OpenMetadata

from app.config import Settings


class OpenMetadataReader:
    def __init__(self, settings: Settings):
        connection = OpenMetadataConnection(
            hostPort=settings.omd_host,
            authProvider=AuthProvider.openmetadata,
            securityConfig=OpenMetadataJWTClientConfig(jwtToken=settings.omd_token),
        )
        self._client = OpenMetadata(
            connection,
            additional_client_config_arguments={"timeout": settings.request_timeout_seconds},
        )

    def list_entities(self, *, entity, fields: list[str], params: dict[str, str | int]):
        sdk_params = {key: value for key, value in params.items() if key not in {"after", "limit"}}
        return self._client.list_entities(
            entity=entity,
            fields=fields,
            params=sdk_params,
            limit=int(params.get("limit", 100)),
            after=params.get("after"),
        )

    def get_by_id(self, *, entity, entity_id: str, fields: list[str]):
        return self._client.get_by_id(entity=entity, entity_id=entity_id, fields=fields)
