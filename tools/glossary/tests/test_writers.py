import csv
from pathlib import Path

from tools.glossary.model import GLOSSARY_NAME, Term
from tools.glossary.writers import (
    derive_fk_relations,
    write_glossary_csv,
    write_mapping_csv,
    write_relationships_csv,
)

HEADER = ["parent", "name*", "displayName", "description", "synonyms", "relatedTerms",
          "references", "tags", "reviewers", "owner", "glossaryStatus", "color",
          "iconURL", "domains", "extension"]
G = GLOSSARY_NAME

SALES = Term("Sales", None, "Approved", "Selling.")
ORDER = Term("Sales Order", "Sales", "Approved", "An order.", synonyms=["Order", "SO"],
             objects=["AdventureWorks2019.Sales.SalesOrderHeader"],
             columns=["AdventureWorks2019.Sales.SalesOrderHeader.SalesOrderID"],
             related=[{"type": "partOf", "term": "Sales.Customer"}, {"type": "relatedTo", "term": "Sales.Customer"}])
CUSTOMER = Term("Customer", "Sales", "Draft", "A buyer.", objects=["AdventureWorks2019.Sales.Customer"])


def read(path: Path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_header_matches_omd_columns(tmp_path):
    out = tmp_path / "g.csv"
    write_glossary_csv([SALES], out)
    assert out.read_text(encoding="utf-8").splitlines()[0].split(",") == HEADER


def test_glossary_csv_round_trips_awkward_text(tmp_path):
    awkward = 'Has, comma, a "quote",\nnewline and **bold**.'
    out = tmp_path / "g.csv"
    write_glossary_csv([Term("Sales", None, "Approved", awkward)], out)
    assert read(out)[0]["description"] == awkward


def test_roots_precede_children_and_parent_is_fqn(tmp_path):
    out = tmp_path / "g.csv"
    write_glossary_csv([ORDER, SALES, CUSTOMER], out)
    rows = read(out)
    assert [r["name*"] for r in rows] == ["Sales", "Sales Order", "Customer"]
    assert rows[0]["parent"] == ""
    assert rows[1]["parent"] == f"{G}.Sales"
    assert rows[1]["displayName"] == "Sales Order"
    assert rows[1]["synonyms"] == "Order;SO"
    assert rows[2]["glossaryStatus"] == "Draft"


def test_related_terms_are_typed_and_semicolon_joined(tmp_path):
    out = tmp_path / "g.csv"
    write_glossary_csv([SALES, ORDER, CUSTOMER], out)
    assert read(out)[1]["relatedTerms"] == f"partOf:{G}.Sales.Customer;relatedTo:{G}.Sales.Customer"


def test_mapping_csv_has_table_and_column_rows(tmp_path):
    out = tmp_path / "m.csv"
    write_mapping_csv([SALES, ORDER], out)
    rows = read(out)
    assert [(r["object_type"], r["object_fqn"]) for r in rows] == [
        ("table", "MSSQL Desktop.AdventureWorks2019.Sales.SalesOrderHeader"),
        ("column", "MSSQL Desktop.AdventureWorks2019.Sales.SalesOrderHeader.SalesOrderID"),
    ]
    assert rows[0]["term_fqn"] == f"{G}.Sales.Sales Order"


def fk_table(name, refers_to):
    return {
        "fullyQualifiedName": f"MSSQL Desktop.AdventureWorks2019.Sales.{name}",
        "tableConstraints": [{"constraintType": "FOREIGN_KEY", "columns": ["CustomerID"],
                              "referredColumns": [f"MSSQL Desktop.AdventureWorks2019.Sales.{refers_to}.CustomerID"]}],
    }


def test_derive_fk_relations_skips_same_term_and_dedupes():
    snapshot = {"service": "MSSQL Desktop", "databases": {"AdventureWorks2019": [
        fk_table("SalesOrderHeader", "Customer"),
        fk_table("SalesOrderHeader2", "Customer"),
        fk_table("Customer", "Customer"),
    ]}}
    order = Term("Sales Order", "Sales", "Approved", "o", objects=[
        "AdventureWorks2019.Sales.SalesOrderHeader", "AdventureWorks2019.Sales.SalesOrderHeader2"])
    customer = Term("Customer", "Sales", "Approved", "c", objects=["AdventureWorks2019.Sales.Customer"])
    rels = derive_fk_relations([order, customer], snapshot)
    assert len(rels) == 1
    assert rels[0]["subject"] == f"{G}.Sales.Sales Order"
    assert rels[0]["object"] == f"{G}.Sales.Customer"
    assert rels[0]["relation"] == "references"
    assert rels[0]["evidence"].startswith("fk: ")


def test_curated_relation_overrides_derived(tmp_path):
    s, o = f"{G}.Sales.Sales Order", f"{G}.Sales.Customer"
    derived = [{"subject": s, "relation": "references", "object": o, "evidence": "fk: x"}]
    curated = [{"subject": s, "relation": "placed by", "object": o, "evidence": "business rule"}]
    out = tmp_path / "r.csv"
    write_relationships_csv(curated, derived, out)
    rows = read(out)
    assert [(r["relation"], r["source"]) for r in rows] == [("placed by", "curated")]


def test_glossary_csv_without_related_terms_leaves_column_empty(tmp_path):
    out = tmp_path / "g.csv"
    write_glossary_csv([SALES, ORDER, CUSTOMER], out, include_related=False)
    assert all(r["relatedTerms"] == "" for r in read(out))
    assert [r["name*"] for r in read(out)] == ["Sales", "Sales Order", "Customer"]


def test_mapping_marks_tables_without_omd_description_as_inferred(tmp_path):
    snapshot = {"service": "MSSQL Desktop", "databases": {"AdventureWorks2019": [
        {"fullyQualifiedName": "MSSQL Desktop.AdventureWorks2019.Sales.SalesOrderHeader", "description": "General sales order information."},
        {"fullyQualifiedName": "MSSQL Desktop.AdventureWorks2019.Sales.Customer"}]}}
    two = Term("Sales Order", "Sales", "Approved", "o", basis="name", objects=[
        "AdventureWorks2019.Sales.SalesOrderHeader", "AdventureWorks2019.Sales.Customer"])
    out = tmp_path / "m.csv"
    write_mapping_csv([two], out, snapshot)
    assert [r["basis"] for r in read(out)] == ["name", "inferred"]


def test_related_terms_only_point_at_rows_later_in_the_file(tmp_path):
    # OMD's import fails with "Entity not found" when a row relates to a term already updated earlier in the same file.
    cust = Term("Customer", "Sales", "Draft", "A buyer.", related=[{"type": "relatedTo", "term": "Sales.Sales Order"}])
    order = Term("Sales Order", "Sales", "Approved", "An order.", related=[{"type": "relatedTo", "term": "Sales.Customer"}])
    out = tmp_path / "g.csv"
    write_glossary_csv([SALES, cust, order], out)
    assert [r["relatedTerms"] for r in read(out)] == ["", f"relatedTo:{G}.Sales.Sales Order", ""]
