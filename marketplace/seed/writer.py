"""Idempotent create-or-update helpers. They set only the fields the demo owns and never touch table metadata."""
from urllib.parse import quote

from app.omd import OmdClient, OmdError
from seed import definitions as d


class SeedError(Exception):
    pass


def _find(client: OmdClient, path: str, params: dict | None = None) -> dict | None:
    try:
        return client.get(path, params)
    except OmdError as err:
        if err.status == 404:
            return None
        raise


def ensure_user(client: OmdClient, user: d.UserDef) -> None:
    client.put("/users", {"name": user.name, "displayName": user.display_name, "email": user.email})


def ensure_team(client: OmdClient, team: d.TeamDef) -> None:
    client.put("/teams", {"name": team.name, "displayName": team.display_name, "teamType": "Group"})


def ensure_domain(client: OmdClient, name: str) -> None:
    client.put("/domains", {"name": name, "displayName": name, "description": f"{name} data", "domainType": "Aggregate"})


def ensure_classification_tags(client: OmdClient, classification: str = d.SENSITIVITY_CLASSIFICATION,
                               tags: tuple[str, ...] = ("Public", "Internal", "Confidential")) -> None:
    client.put("/classifications", {"name": classification, "description": "Data sensitivity levels used by the marketplace demo"})
    for tag in tags:
        client.put("/tags", {"classification": classification, "name": tag, "description": f"{tag} data"})


def ensure_custom_property(client: OmdClient, entity_type: str = "dataProduct", name: str = d.ENTRA_PROPERTY) -> None:
    types = client.get("/metadata/types", {"limit": 200}).get("data", [])
    entity = next(t for t in types if t["name"] == entity_type)
    string_type = next(t for t in types if t["name"] == "string")
    current = client.get(f"/metadata/types/{entity['id']}", {"fields": "customProperties"})
    if any(p["name"] == name for p in current.get("customProperties") or []):
        return
    client.put(f"/metadata/types/{entity['id']}", {
        "name": name,
        "description": "MS Entra group whose membership grants access to this data product",
        "propertyType": {"id": string_type["id"], "type": "type"},
    })


def _table_refs(client: OmdClient, tables: list[str]) -> list[dict]:
    refs, missing = [], []
    for fqn in tables:
        table = _find(client, f"/tables/name/{quote(fqn, safe='')}")
        if table is None:
            missing.append(fqn)
        else:
            refs.append({"id": table["id"], "type": "table"})
    if missing:
        raise SeedError("Tables not found in OpenMetadata: " + ", ".join(missing))
    return refs


def ensure_product(client: OmdClient, product: d.ProductDef) -> str:
    refs = _table_refs(client, product.tables)
    owner = client.get(f"/users/name/{product.owner}")
    tags = [{"tagFQN": f"{d.SENSITIVITY_CLASSIFICATION}.{product.sensitivity_tag}",
             "source": "Classification", "labelType": "Manual", "state": "Confirmed"}]
    created = client.put("/dataProducts", {
        "name": product.name, "displayName": product.display_name, "description": product.description,
        "domains": [product.domain], "owners": [{"id": owner["id"], "type": "user"}],
        "experts": [product.steward], "tags": tags,
        "extension": {d.ENTRA_PROPERTY: product.entra_group},
    })
    # OMD only accepts an asset into a data product when the asset is already in the product's domain.
    client.put(f"/domains/{quote(product.domain, safe='')}/assets/add", {"assets": refs})
    client.put(f"/dataProducts/{quote(product.name, safe='')}/assets/add", {"assets": refs})
    wanted = f"Certification.{product.certification}"
    current = client.get(f"/dataProducts/name/{product.name}", {"fields": "certification"})
    if ((current.get("certification") or {}).get("tagLabel") or {}).get("tagFQN") != wanted:
        client.patch(f"/dataProducts/{created['id']}", [{"op": "add", "path": "/certification", "value": {
            "tagLabel": {"tagFQN": wanted, "source": "Classification", "labelType": "Manual", "state": "Confirmed"}}}])
    return product.name
