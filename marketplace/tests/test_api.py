import httpx
import pytest
from fastapi.testclient import TestClient

from app import main
from app.catalog import CatalogService
from app.omd import OmdClient
from app.requests_store import AccessRequestStore
from tests.conftest import make_settings
from tests.fake_omd import FakeOmd


@pytest.fixture
def client():
    omd = OmdClient(make_settings(), transport=httpx.MockTransport(FakeOmd()))
    catalog = CatalogService(omd, ttl_seconds=30)
    store = AccessRequestStore()
    main.app.dependency_overrides[main.get_catalog] = lambda: catalog
    main.app.dependency_overrides[main.get_store] = lambda: store
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


def test_list_returns_items_and_facets(client):
    body = client.get("/api/products").json()
    assert {p["name"] for p in body["items"]} == {"internet-sales-mart", "empty-product"}
    assert body["facets"]["domain"] == ["Sales"]


def test_domain_filter(client):
    items = client.get("/api/products", params={"domain": "Sales"}).json()["items"]
    assert [p["name"] for p in items] == ["internet-sales-mart"]
    assert client.get("/api/products", params={"domain": "Nope"}).json()["items"] == []


def test_detail_and_404(client):
    assert client.get("/api/products/internet-sales-mart").json()["datasets"][0]["name"] == "FactInternetSales"
    assert client.get("/api/products/nope").status_code == 404


def test_request_validation(client):
    ok = {"product": "internet-sales-mart", "justification": "Need it", "duration": "90 days"}
    assert client.post("/api/access-requests", json={**ok, "justification": "   "}).status_code == 422
    assert client.post("/api/access-requests", json={**ok, "product": "nope"}).status_code == 404
    assert client.post("/api/access-requests", json={**ok, "product": "empty-product"}).status_code == 409


def test_request_numbers_increment_and_round_trip(client):
    ok = {"product": "internet-sales-mart", "justification": "Need it", "duration": "90 days"}
    first = client.post("/api/access-requests", json=ok).json()
    second = client.post("/api/access-requests", json=ok).json()
    assert (first["number"], second["number"]) == ("REQ0010001", "REQ0010002")
    got = client.get(f"/api/access-requests/{first['number']}").json()
    assert got["user"] == "John Analyst Doe"
    assert got["entra_group"] == "GRP-DW-SALES-ISM-READ"
    assert got["product_title"] == "Internet Sales Mart"
    assert client.get("/api/access-requests/REQ9999999").status_code == 404
