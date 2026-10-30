"""Table-level lineage edges between existing tables."""
from urllib.parse import quote

from app.omd import OmdClient
from seed.writer import SeedError, _find


def _ref(client: OmdClient, fqn: str) -> dict:
    table = _find(client, f"/tables/name/{quote(fqn, safe='')}")
    if table is None:
        raise SeedError(f"Table not found in OpenMetadata: {fqn}")
    return {"id": table["id"], "type": "table"}


def ensure_edges(client: OmdClient, edges: list[tuple[str, str]]) -> None:
    for upstream, downstream in edges:
        client.put("/lineage", {"edge": {
            "fromEntity": _ref(client, upstream), "toEntity": _ref(client, downstream),
            "lineageDetails": {"description": "Demo lineage"},
        }})
