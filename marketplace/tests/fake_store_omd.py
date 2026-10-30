"""A stateful fake OMD for seed tests: remembers PUT/POST entities, supports name lookups and PATCH."""
import json
import uuid
from urllib.parse import unquote

import httpx

COLLECTIONS = ("users", "teams", "domains", "classifications", "tags", "dataProducts", "dataQuality/testCases")


class StoreOmd:
    def __init__(self, existing_tables: list[str]):
        self.entities: dict[str, dict[str, dict]] = {c: {} for c in COLLECTIONS}
        self.tables = {
            fqn: {"id": f"id-{i}", "name": fqn.rsplit(".", 1)[-1], "fullyQualifiedName": fqn, "columns": [],
                  "tags": [{"tagFQN": "Glossary.Existing", "source": "Glossary"}], "description": "keep me"}
            for i, fqn in enumerate(existing_tables)
        }
        self.type = {"id": "type-1", "name": "dataProduct", "customProperties": []}
        self.writes: list[tuple[str, str, object]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path.removeprefix("/api/v1")
        body = json.loads(request.content) if request.content else None
        method = request.method
        if method != "GET":
            self.writes.append((method, path, body))
        if path == "/metadata/types" and method == "GET":
            return httpx.Response(200, json={"data": [self.type, {"id": "string-1", "name": "string"}], "paging": {}})
        if path.startswith("/metadata/types/"):
            if method == "PUT":
                props = [p for p in self.type["customProperties"] if p["name"] != body["name"]]
                self.type["customProperties"] = props + [body]
            return httpx.Response(200, json=self.type)
        if path.startswith("/tables/name/"):
            fqn = unquote(path.removeprefix("/tables/name/"))
            return httpx.Response(200, json=self.tables[fqn]) if fqn in self.tables else httpx.Response(404, json={})
        if method == "PATCH" and path.startswith("/tables/"):
            table = next(t for t in self.tables.values() if t["id"] == path.rsplit("/", 1)[-1])
            for op in body:
                table[op["path"].lstrip("/")] = op["value"]
            return httpx.Response(200, json=table)
        if method == "PUT" and path == "/dataQuality/testCases":
            key = f"{body['entityLink']}|{body['name']}"
            table_fqn = body["entityLink"].split("::")[2].rstrip(">")
            self.entities["dataQuality/testCases"][key] = {**body, "fullyQualifiedName": f"{table_fqn}.{body['name']}"}
            return httpx.Response(201, json=self.entities["dataQuality/testCases"][key])
        if method == "POST" and path.startswith("/dataQuality/testCases/testCaseResults/"):
            return httpx.Response(200, json={})
        if method == "PUT" and path == "/lineage":
            return httpx.Response(200, json={})
        if method == "PUT" and path.endswith("/assets/add"):
            return httpx.Response(200, json={"status": "success"})
        for collection in COLLECTIONS:
            if path == f"/{collection}" and method in ("PUT", "POST"):
                key = body.get("name") if collection != "tags" else f"{body['classification']}.{body['name']}"
                existing = self.entities[collection].get(key, {})
                self.entities[collection][key] = {**existing, **body, "id": existing.get("id", str(uuid.uuid4()))}
                return httpx.Response(201, json=self.entities[collection][key])
            if path.startswith(f"/{collection}/name/") and method == "GET":
                key = unquote(path.removeprefix(f"/{collection}/name/"))
                found = self.entities[collection].get(key)
                return httpx.Response(200, json=found) if found else httpx.Response(404, json={})
            if path.startswith(f"/{collection}/") and method == "PATCH":
                entity = next(e for e in self.entities[collection].values() if e["id"] == path.rsplit("/", 1)[-1])
                for op in body:
                    entity[op["path"].lstrip("/")] = op["value"]
                return httpx.Response(200, json=entity)
        return httpx.Response(404, json={"message": f"unexpected {method} {path}"})
