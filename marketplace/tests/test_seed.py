import httpx
import pytest

from app.omd import OmdClient
from seed import definitions as d
from seed.seed import run_base_seed
from seed.writer import SeedError, ensure_product
from tests.conftest import make_settings
from tests.fake_store_omd import StoreOmd


def all_tables() -> list[str]:
    return sorted({t for p in d.PRODUCTS for t in p.tables})


@pytest.fixture
def omd():
    store = StoreOmd(all_tables())
    return store, OmdClient(make_settings(), transport=httpx.MockTransport(store))


def test_seed_twice_creates_the_same_things(omd):
    store, client = omd
    run_base_seed(client)
    first = {c: dict(v) for c, v in store.entities.items()}
    writes_before = len(store.writes)
    run_base_seed(client)
    assert {c: set(v) for c, v in store.entities.items()} == {c: set(v) for c, v in first.items()}
    second_writes = store.writes[writes_before:]
    assert not [w for w in second_writes if w[0] == "PATCH"], "certification must not be re-patched"


def test_seven_products_with_entra_property(omd):
    store, client = omd
    run_base_seed(client)
    products = store.entities["dataProducts"]
    assert len(products) == 7
    assert products["internet-sales-mart"]["extension"] == {"entraGroup": d.PRODUCTS[0].entra_group}
    assert [p["name"] for p in store.type["customProperties"]] == ["entraGroup"]


def test_missing_table_raises_and_writes_nothing(omd):
    store, client = omd
    run_base_seed(client)  # so owners/domains exist
    del store.tables[d.PRODUCTS[0].tables[0]]
    store.entities["dataProducts"].clear()
    writes_before = len(store.writes)
    with pytest.raises(SeedError) as exc:
        ensure_product(client, d.PRODUCTS[0])
    assert d.PRODUCTS[0].tables[0] in str(exc.value)
    assert [w for w in store.writes[writes_before:] if w[1] == "/dataProducts"] == []


def test_no_write_touches_existing_table_metadata(omd):
    store, client = omd
    run_base_seed(client)
    assert not [w for w in store.writes if w[1].startswith("/tables")]


def test_internal_products_carry_the_sensitivity_tag(omd):
    store, client = omd
    run_base_seed(client)
    tags = store.entities["dataProducts"]["purchasing-spend"]["tags"]
    assert {"tagFQN": "Sensitivity.Internal", "source": "Classification", "labelType": "Manual", "state": "Confirmed"} in tags


def test_tables_join_the_domain_before_the_product(omd):
    store, client = omd
    run_base_seed(client)
    paths = [w[1] for w in store.writes if w[1].endswith("/assets/add")]
    product = d.PRODUCTS[0]
    assert paths.index(f"/domains/{product.domain}/assets/add") < paths.index(f"/dataProducts/{product.name}/assets/add")
    domain_write = next(w for w in store.writes if w[1] == f"/domains/{product.domain}/assets/add")
    assert len(domain_write[2]["assets"]) == len(product.tables)
    assert all(a["type"] == "table" for a in domain_write[2]["assets"])


def test_every_product_has_an_explicit_sensitivity_tag(omd):
    store, client = omd
    run_base_seed(client)
    for name, product in store.entities["dataProducts"].items():
        assert any(t["tagFQN"].startswith("Sensitivity.") for t in product["tags"]), name
    assert set(store.entities["tags"]) >= {"Sensitivity.Public", "Sensitivity.Internal", "Sensitivity.Confidential"}


def test_descriptions_are_added_only_where_empty(omd):
    from seed.writer import ensure_table_descriptions

    store, client = omd
    empty, described = list(d.DESCRIPTIONS)[0], d.PRODUCTS[2].tables[0]
    store.tables[empty]["description"] = ""
    ensure_table_descriptions(client, {empty: "New text", described: "Should not be written"})
    patches = [w for w in store.writes if w[0] == "PATCH" and w[1].startswith("/tables/")]
    assert len(patches) == 1
    assert patches[0][2] == [{"op": "add", "path": "/description", "value": "New text"}]
