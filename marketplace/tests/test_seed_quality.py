import httpx
import pytest

from app.omd import OmdClient
from seed import definitions as d
from seed.lineage import ensure_edges
from seed.quality import ensure_test
from seed.seed import run_full_seed
from seed.writer import SeedError
from tests.conftest import make_settings
from tests.fake_store_omd import StoreOmd


def all_tables() -> list[str]:
    return sorted({t for p in d.PRODUCTS for t in p.tables} | {t for pair in d.LINEAGE for t in pair})


@pytest.fixture
def omd():
    store = StoreOmd(all_tables())
    return store, OmdClient(make_settings(), transport=httpx.MockTransport(store))


def results(store):
    return [w[2] for w in store.writes if w[1].startswith("/dataQuality/testCases/testCaseResults/")]


def test_ensure_test_creates_case_then_posts_the_chosen_outcome(omd):
    store, client = omd
    table = d.PRODUCTS[0].tables[0]
    ensure_test(client, d.TestDef(table, "row_count_positive", "tableRowCountToBeBetween",
                                  [{"name": "minValue", "value": "1"}], "Failed"))
    created = [w for w in store.writes if w[1] == "/dataQuality/testCases"][0][2]
    assert created["entityLink"] == f"<#E::table::{table}>"
    assert created["testDefinition"] == "tableRowCountToBeBetween"
    assert results(store)[0]["testCaseStatus"] == "Failed"


def test_rerun_reuses_the_case_and_reposts_the_result(omd):
    store, client = omd
    defn = d.TestDef(d.PRODUCTS[0].tables[0], "row_count_positive", "tableRowCountToBeBetween", [], "Success")
    ensure_test(client, defn)
    ensure_test(client, defn)
    assert len(store.entities["dataQuality/testCases"]) == 1
    assert len(results(store)) == 2


def test_build_tests_covers_every_unique_table_twice_with_spread_outcomes():
    tests = d.build_tests()
    tables = {t for p in d.PRODUCTS for t in p.tables}
    assert {t.table for t in tests} == tables
    assert len(tests) == 2 * len(tables)
    assert {t.outcome for t in tests} == {"Success", "Failed"}


def test_lineage_edge_payload_and_missing_table(omd):
    store, client = omd
    ensure_edges(client, [d.LINEAGE[0]])
    edge = [w for w in store.writes if w[1] == "/lineage"][0][2]["edge"]
    assert edge["fromEntity"]["type"] == "table" and edge["toEntity"]["type"] == "table"
    with pytest.raises(SeedError):
        ensure_edges(client, [("nope.nothing", d.LINEAGE[0][1])])


def test_full_seed_is_repeatable(omd):
    store, client = omd
    run_full_seed(client)
    run_full_seed(client)
    assert len(store.entities["dataQuality/testCases"]) == len(d.build_tests())
