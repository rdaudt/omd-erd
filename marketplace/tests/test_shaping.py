from app.models import ProductSummary
from app.shaping import (
    derive_sensitivity,
    facets,
    filter_products,
    product_quality,
    quality_bucket,
    table_quality,
)


def make(name="p", **kw) -> ProductSummary:
    base = dict(
        name=name, display_name=name.title(), description="d", domain="Sales", owners=["Ann"],
        steward=None, certification="Gold", table_count=1, quality=95, sensitivity="Public",
        entra_group="G", glossary_terms=[], tags=[],
    )
    return ProductSummary(**{**base, **kw})


def test_table_quality_is_pass_percent():
    assert table_quality(["Success", "Failed", "Success", "Success"]) == 75
    assert table_quality([]) is None


def test_product_quality_means_non_none_scores():
    assert product_quality([100, None, 80]) == 90
    assert product_quality([None]) is None
    assert product_quality([]) is None


def test_quality_buckets():
    assert [quality_bucket(s) for s in (90, 89, 70, 69, None)] == ["90+", "70-89", "70-89", "<70", "n/a"]


def test_sensitivity_highest_wins():
    assert derive_sensitivity(["PII.Sensitive", "Sensitivity.Internal"]) == "Confidential"
    assert derive_sensitivity(["PersonalData.Personal"]) == "Confidential"
    assert derive_sensitivity(["Sensitivity.Internal"]) == "Internal"
    assert derive_sensitivity([]) == "Public"


def test_filters_combine_with_and():
    ps = [make("a", domain="Sales"), make("b", domain="HR", certification="Silver")]
    assert [p.name for p in filter_products(ps, domain="HR")] == ["b"]
    assert filter_products(ps, domain="HR", certification="Gold") == []
    assert filter_products(ps, domain="Nope") == []


def test_quality_filter_uses_buckets():
    ps = [make("a", quality=95), make("b", quality=75), make("c", quality=None)]
    assert [p.name for p in filter_products(ps, quality="70-89")] == ["b"]
    assert [p.name for p in filter_products(ps, quality="n/a")] == ["c"]


def test_owner_filter_matches_any_owner():
    ps = [make("a", owners=["Ann", "Bob"]), make("b", owners=["Cy"])]
    assert [p.name for p in filter_products(ps, owner="Bob")] == ["a"]


def test_q_searches_glossary_terms_case_insensitively():
    ps = [make("a", glossary_terms=["Customer"]), make("b")]
    assert [p.name for p in filter_products(ps, q="custom")] == ["a"]


def test_facets_on_empty_list_are_empty():
    assert facets([]) == {k: [] for k in ("domain", "sensitivity", "quality", "owner", "certification")}


def test_facets_list_distinct_sorted_values():
    ps = [make("a", domain="Sales", quality=95), make("b", domain="HR", quality=None, certification=None)]
    f = facets(ps)
    assert f["domain"] == ["HR", "Sales"]
    assert f["quality"] == ["90+", "n/a"]
    assert f["certification"] == ["Gold"]
