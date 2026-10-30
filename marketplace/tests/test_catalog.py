import httpx
import pytest

from app.catalog import CatalogService
from app.omd import OmdClient
from tests.conftest import make_settings
from tests.fake_omd import DIM, FACT, FakeOmd


@pytest.fixture
def fake():
    return FakeOmd()


@pytest.fixture
def service(fake):
    client = OmdClient(make_settings(), transport=httpx.MockTransport(fake))
    return CatalogService(client, ttl_seconds=30)


def by_name(products):
    return {p.name: p for p in products}


def test_full_product_is_summarised(service):
    p = by_name(service.list_products())["internet-sales-mart"]
    assert (p.display_name, p.domain, p.owners, p.steward) == ("Internet Sales Mart", "Sales", ["Maria Chen"], "Lee Park")
    assert (p.certification, p.entra_group) == ("Gold", "GRP-DW-SALES-ISM-READ")
    assert (p.table_count, p.quality, p.sensitivity) == (1, 75, "Confidential")
    assert p.glossary_terms == ["Glossary.Customer"]


def test_empty_product_has_no_quality_and_no_entra_group(service):
    p = by_name(service.list_products())["empty-product"]
    assert (p.table_count, p.quality, p.entra_group, p.certification, p.domain) == (0, None, None, None, None)
    assert p.sensitivity == "Public"


def test_views_are_excluded_from_datasets(service):
    detail = service.get_product("internet-sales-mart")
    assert [d.fqn for d in detail.datasets] == [FACT]
    assert detail.datasets[0].quality == 75
    assert detail.datasets[0].description == "Fact table"


def test_detail_has_tests_and_lineage(service):
    detail = service.get_product("internet-sales-mart")
    assert [t.status for t in detail.tests] == ["Success", "Success", "Success", "Failed"]
    assert detail.lineage.edges == [(DIM, FACT)], "edges to views are dropped"
    assert set(detail.lineage.nodes) == {DIM, FACT}


def test_unknown_product_returns_none(service):
    assert service.get_product("nope") is None


def test_second_call_within_ttl_makes_no_extra_requests(service, fake):
    service.list_products()
    n = len(fake.requests)
    service.list_products()
    assert len(fake.requests) == n


def test_non_table_lineage_neighbours_are_ignored_without_failing(service, fake):
    detail = service.get_product("internet-sales-mart")
    assert all("Dashboard" not in n for n in detail.lineage.nodes)
    assert not [r for r in fake.requests if "SalesDashboard" in r], "must not look a dashboard up as a table"


def test_custom_certification_value_passes_through(fake, monkeypatch):
    from tests import fake_omd

    custom = [{**fake_omd.PRODUCTS[0], "certification": {"tagLabel": {"tagFQN": "Certification.Platinum"}}}]
    monkeypatch.setattr(fake_omd, "PRODUCTS", custom)
    client = OmdClient(make_settings(), transport=httpx.MockTransport(fake))
    products = CatalogService(client, ttl_seconds=0).list_products()
    assert products[0].certification == "Platinum"
