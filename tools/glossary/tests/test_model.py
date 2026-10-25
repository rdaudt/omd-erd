import json
from dataclasses import replace
from pathlib import Path

from tools.glossary.model import Term, load_exclusions, load_terms, validate


def table(db, schema, name, columns=("ID",)):
    return {
        "name": name,
        "fullyQualifiedName": f"MSSQL Desktop.{db}.{schema}.{name}",
        "columns": [{"name": c} for c in columns],
        "tableConstraints": [],
    }


SNAPSHOT = {
    "service": "MSSQL Desktop",
    "databases": {
        "AdventureWorks2019": [
            table("AdventureWorks2019", "Sales", "SalesOrderHeader"),
            table("AdventureWorks2019", "Sales", "Customer"),
        ],
        "AdventureWorksDW2019": [table("AdventureWorksDW2019", "dbo", "DimCustomer")],
    },
}

SALES = Term(name="Sales", parent=None, status="Approved", description="Selling.")
ORDER = Term(
    name="Sales Order",
    parent="Sales",
    status="Approved",
    description="An order.",
    objects=["AdventureWorks2019.Sales.SalesOrderHeader"],
)
CUSTOMER = Term(
    name="Customer",
    parent="Sales",
    status="Approved",
    description="A buyer.",
    objects=["AdventureWorks2019.Sales.Customer", "AdventureWorksDW2019.dbo.DimCustomer"],
)


def terms():
    return [SALES, ORDER, CUSTOMER]


def errors(ts=None, exclusions=None, schemas=None):
    return validate(ts if ts is not None else terms(), SNAPSHOT, exclusions or {}, schemas)


def has(errs, text):
    return any(text in e for e in errs)


def test_valid_data_has_no_errors():
    assert errors() == []


def test_duplicate_path_is_reported():
    assert has(errors(terms() + [ORDER]), "duplicate")


def test_dot_in_term_name_is_rejected():
    assert has(errors(terms() + [replace(ORDER, name="Sales.Order")]), "contains a dot")


def test_missing_parent_is_reported():
    assert has(errors([ORDER, CUSTOMER]), "parent")


def test_parent_must_be_root():
    deep = replace(ORDER, name="Line", parent="Sales.Sales Order")
    assert has(errors(terms() + [deep]), "root")


def test_invalid_status_is_reported():
    assert has(errors([SALES, replace(ORDER, status="Final"), CUSTOMER]), "status")


def test_approved_term_needs_operational_object():
    dw_only = replace(CUSTOMER, objects=["AdventureWorksDW2019.dbo.DimCustomer"])
    errs = errors([SALES, ORDER, dw_only], exclusions={"AdventureWorks2019.Sales.Customer": "x"})
    assert has(errs, "Draft")


def test_non_root_term_needs_an_object():
    assert has(errors(terms() + [replace(ORDER, name="Empty", objects=[])]), "no objects")


def test_unknown_object_names_the_table():
    bad = replace(ORDER, objects=["AdventureWorks2019.Sales.Gone"])
    assert has(errors([SALES, bad, CUSTOMER]), "AdventureWorks2019.Sales.Gone")


def test_unknown_column_is_reported():
    bad = replace(ORDER, columns=["AdventureWorks2019.Sales.SalesOrderHeader.Nope"])
    assert has(errors([SALES, bad, CUSTOMER]), "SalesOrderHeader.Nope")


def test_related_term_must_exist():
    bad = replace(ORDER, related=[{"type": "partOf", "term": "Sales.Ghost"}])
    assert has(errors([SALES, bad, CUSTOMER]), "Sales.Ghost")


def test_related_type_must_be_valid():
    bad = replace(ORDER, related=[{"type": "likes", "term": "Sales.Customer"}])
    assert has(errors([SALES, bad, CUSTOMER]), "likes")


def test_unmapped_table_is_reported_unless_excluded():
    only_order = [SALES, ORDER]
    assert has(errors(only_order), "AdventureWorks2019.Sales.Customer")
    ex = {"AdventureWorks2019.Sales.Customer": "x", "AdventureWorksDW2019.dbo.DimCustomer": "x"}
    assert errors(only_order, exclusions=ex) == []


def test_schemas_filter_limits_coverage_check():
    errs = errors([SALES, ORDER], schemas={"AdventureWorks2019.Sales"})
    assert has(errs, "Customer") and not has(errs, "DimCustomer")


def test_load_terms_and_exclusions(tmp_path: Path):
    (tmp_path / "terms").mkdir()
    (tmp_path / "terms" / "a.json").write_text(
        json.dumps([{"name": "Sales", "parent": None, "status": "Approved", "description": "d"}]),
        encoding="utf-8",
    )
    (tmp_path / "exclusions.json").write_text(json.dumps({"A.b.c": "why"}), encoding="utf-8")
    loaded = load_terms(tmp_path)
    assert loaded[0].fqn == "AdventureWorks Business Glossary.Sales"
    assert loaded[0].objects == []
    assert load_exclusions(tmp_path) == {"A.b.c": "why"}


def test_abstract_term_may_have_no_objects():
    concept = replace(ORDER, name="Concept", objects=[], abstract=True)
    assert errors(terms() + [concept]) == []
