"""A tiny in-memory OMD used by catalog and API tests."""
import httpx

FACT = "svc.db.sales.FactInternetSales"
DIM = "svc.db.sales.DimCustomer"
VIEW = "svc.db.sales.vSales"


def tag(fqn, source="Classification"):
    return {"tagFQN": fqn, "source": source}


PRODUCTS = [
    {
        "name": "internet-sales-mart", "displayName": "Internet Sales Mart", "description": "Online sales.",
        "domains": [{"name": "Sales", "displayName": "Sales"}],
        "owners": [{"name": "maria.chen", "displayName": "Maria Chen"}],
        "experts": [{"name": "lee.park", "displayName": "Lee Park"}],
        "assets": [
            {"type": "table", "fullyQualifiedName": FACT, "id": "t1"},
            {"type": "table", "fullyQualifiedName": VIEW, "id": "t2"},
        ],
        "tags": [tag("Glossary.Customer", "Glossary")],
        "extension": {"entraGroup": "GRP-DW-SALES-ISM-READ"},
        "certification": {"tagLabel": {"tagFQN": "Certification.Gold"}},
    },
    {"name": "empty-product", "displayName": "Empty Product", "description": "", "assets": [], "tags": []},
]

TABLES = {
    FACT: {"id": "t1", "name": "FactInternetSales", "fullyQualifiedName": FACT, "description": "Fact table",
           "tableType": "Regular", "tags": [],
           "columns": [{"name": "Email", "tags": [tag("PII.Sensitive")]}]},
    DIM: {"id": "d1", "name": "DimCustomer", "fullyQualifiedName": DIM, "description": "", "tableType": "Regular",
          "tags": [], "columns": []},
    VIEW: {"id": "t2", "name": "vSales", "fullyQualifiedName": VIEW, "description": "", "tableType": "View",
           "tags": [], "columns": []},
}

TEST_RESULTS = {FACT: ["Success", "Success", "Success", "Failed"]}


class FakeOmd:
    def __init__(self):
        self.requests: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path.removeprefix("/api/v1")
        self.requests.append(path)
        if path == "/dataProducts":
            return httpx.Response(200, json={"data": [{k: v for k, v in p.items() if k != "assets"} for p in PRODUCTS], "paging": {}})
        if path.startswith("/dataProducts/name/") and path.endswith("/assets"):
            name = path.split("/")[3]
            assets = next(p for p in PRODUCTS if p["name"] == name).get("assets", [])
            return httpx.Response(200, json={"data": assets, "paging": {"total": len(assets)}})
        if path.startswith("/tables/name/"):
            fqn = path.removeprefix("/tables/name/")
            return httpx.Response(200, json=TABLES[fqn])
        if path == "/dataQuality/testCases":
            link = request.url.params["entityLink"]
            fqn = link.split("::")[2].rstrip(">")
            cases = [{"name": f"t{i}", "testCaseResult": {"testCaseStatus": s}}
                     for i, s in enumerate(TEST_RESULTS.get(fqn, []))]
            return httpx.Response(200, json={"data": cases, "paging": {}})
        if path.startswith("/lineage/table/name/"):
            fqn = path.removeprefix("/lineage/table/name/")
            if fqn == FACT:
                return httpx.Response(200, json={
                    "entity": {"id": "t1", "fullyQualifiedName": FACT},
                    "nodes": [{"id": "d1", "type": "table", "fullyQualifiedName": DIM},
                              {"id": "t2", "type": "table", "fullyQualifiedName": VIEW},
                              {"id": "dash1", "type": "dashboard", "fullyQualifiedName": "bi.SalesDashboard"}],
                    "upstreamEdges": [{"fromEntity": "d1", "toEntity": "t1"}],
                    "downstreamEdges": [{"fromEntity": "t1", "toEntity": "t2"}, {"fromEntity": "t1", "toEntity": "dash1"}],
                })
            return httpx.Response(200, json={"entity": {"id": "x", "fullyQualifiedName": fqn},
                                             "nodes": [], "upstreamEdges": [], "downstreamEdges": []})
        return httpx.Response(404, json={"message": f"unexpected {path}"})
