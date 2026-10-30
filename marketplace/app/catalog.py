import time
from urllib.parse import quote

from app.models import (
    DatasetRow,
    LineageGraph,
    ProductDetail,
    ProductSummary,
    TestResultRow,
)
from app.omd import OmdClient
from app.shaping import derive_sensitivity, product_quality, table_quality

PRODUCT_FIELDS = "domains,owners,experts,tags,extension,certification"
TABLE_FIELDS = "tags,columns"


def _label(entity: dict) -> str:
    return entity.get("displayName") or entity.get("name") or ""


def _tag_fqns(tags: list[dict] | None, source: str | None = None) -> list[str]:
    return [t["tagFQN"] for t in tags or [] if source is None or t.get("source") == source]


class CatalogService:
    def __init__(self, client: OmdClient, ttl_seconds: int):
        self._client = client
        self._ttl = ttl_seconds
        self._cache: dict[str, tuple[float, object]] = {}

    def _cached(self, key: str, build):
        hit = self._cache.get(key)
        if hit and time.monotonic() - hit[0] < self._ttl:
            return hit[1]
        value = build()
        self._cache[key] = (time.monotonic(), value)
        return value

    def list_products(self) -> list[ProductSummary]:
        return self._cached("list", lambda: [self._load(p)[0] for p in self._raw_products()])

    def get_product(self, name: str) -> ProductDetail | None:
        return self._cached(f"detail:{name}", lambda: self._build_detail(name))

    def _raw_products(self) -> list[dict]:
        return self._client.list_all("/dataProducts", {"fields": PRODUCT_FIELDS})

    def _tables(self, product: dict) -> list[dict]:
        tables = []
        assets = self._client.list_all(f"/dataProducts/name/{quote(product['name'], safe='')}/assets")
        for asset in assets:
            if asset.get("type") != "table":
                continue
            fqn = asset["fullyQualifiedName"]
            table = self._client.get(f"/tables/name/{quote(fqn, safe='')}", {"fields": TABLE_FIELDS})
            if table.get("tableType") in ("View", "MaterializedView"):
                continue
            tables.append(table)
        return tables

    def _statuses(self, fqn: str) -> list[tuple[str, str]]:
        cases = self._client.list_all(
            "/dataQuality/testCases", {"entityLink": f"<#E::table::{fqn}>", "fields": "testCaseResult"}
        )
        return [(c["name"], (c.get("testCaseResult") or {}).get("testCaseStatus", "")) for c in cases]

    def _load(self, product: dict):
        tables = self._tables(product)
        statuses = {t["fullyQualifiedName"]: self._statuses(t["fullyQualifiedName"]) for t in tables}
        scores = {fqn: table_quality([s for _, s in rows if s]) for fqn, rows in statuses.items()}
        tag_fqns = _tag_fqns(product.get("tags"))
        glossary = _tag_fqns(product.get("tags"), "Glossary")
        classification = _tag_fqns(product.get("tags"), "Classification")
        for table in tables:
            tag_fqns += _tag_fqns(table.get("tags"))
            glossary += _tag_fqns(table.get("tags"), "Glossary")
            classification += _tag_fqns(table.get("tags"), "Classification")
            for column in table.get("columns") or []:
                tag_fqns += _tag_fqns(column.get("tags"))
                glossary += _tag_fqns(column.get("tags"), "Glossary")
        certification = ((product.get("certification") or {}).get("tagLabel") or {}).get("tagFQN")
        experts = product.get("experts") or []
        domains = product.get("domains") or ([product["domain"]] if product.get("domain") else [])
        summary = ProductSummary(
            name=product["name"],
            display_name=_label(product),
            description=product.get("description") or "",
            domain=_label(domains[0]) if domains else None,
            owners=[_label(o) for o in product.get("owners") or []],
            steward=_label(experts[0]) if experts else None,
            certification=certification.rsplit(".", 1)[-1] if certification else None,
            table_count=len(tables),
            quality=product_quality(list(scores.values())),
            sensitivity=derive_sensitivity(tag_fqns),
            entra_group=(product.get("extension") or {}).get("entraGroup"),
            glossary_terms=sorted(set(glossary)),
            tags=sorted(set(classification)),
        )
        return summary, tables, statuses, scores

    def _build_detail(self, name: str) -> ProductDetail | None:
        product = next((p for p in self._raw_products() if p["name"] == name), None)
        if product is None:
            return None
        summary, tables, statuses, scores = self._load(product)
        datasets = [
            DatasetRow(
                name=_label(t), fqn=t["fullyQualifiedName"], description=t.get("description") or "",
                quality=scores[t["fullyQualifiedName"]],
            )
            for t in tables
        ]
        tests = [
            TestResultRow(table=fqn, test=test, status=status)
            for fqn, rows in statuses.items() for test, status in rows
        ]
        return ProductDetail(**summary.model_dump(), datasets=datasets, tests=tests, lineage=self._lineage(tables))

    def _is_view(self, fqn: str) -> bool:
        table = self._client.get(f"/tables/name/{quote(fqn, safe='')}")
        return table.get("tableType") in ("View", "MaterializedView")

    def _lineage(self, tables: list[dict]) -> LineageGraph:
        inside = {t["fullyQualifiedName"] for t in tables}
        views: dict[str, bool] = {}

        def hidden(fqn: str) -> bool:
            if fqn in inside:
                return False
            if fqn not in views:
                views[fqn] = self._is_view(fqn)
            return views[fqn]

        nodes = sorted(inside)
        edges: list[tuple[str, str]] = []
        for fqn in nodes:
            graph = self._client.get(f"/lineage/table/name/{quote(fqn, safe='')}", {"upstreamDepth": 1, "downstreamDepth": 1})
            # Only tables can belong to a data product; dashboards, pipelines etc. are not shown.
            names = {n["id"]: n["fullyQualifiedName"] for n in graph.get("nodes", []) if n.get("type", "table") == "table"}
            names[graph["entity"]["id"]] = graph["entity"]["fullyQualifiedName"]
            for edge in graph.get("upstreamEdges", []) + graph.get("downstreamEdges", []):
                pair = (names.get(edge["fromEntity"]), names.get(edge["toEntity"]))
                if all(pair) and pair not in edges and not hidden(pair[0]) and not hidden(pair[1]):
                    edges.append(pair)
        for pair in edges:
            nodes += [n for n in pair if n not in nodes]
        return LineageGraph(nodes=nodes, edges=edges)
