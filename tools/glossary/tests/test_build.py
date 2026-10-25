import json
from pathlib import Path

from tools.glossary import build
from tools.glossary.omd_client import OmdError

SNAPSHOT = {"service": "MSSQL Desktop", "databases": {"AdventureWorks2019": [{
    "name": "Customer", "fullyQualifiedName": "MSSQL Desktop.AdventureWorks2019.Sales.Customer",
    "columns": [{"name": "ID"}], "tableConstraints": []}], "AdventureWorksDW2019": []}}


def setup(tmp_path: Path, terms: list[dict]):
    data = tmp_path / "data"
    (data / "terms").mkdir(parents=True)
    (data / "terms" / "t.json").write_text(json.dumps(terms), encoding="utf-8")
    (data / "exclusions.json").write_text("{}", encoding="utf-8")
    snap = tmp_path / "snapshot.json"
    snap.write_text(json.dumps(SNAPSHOT), encoding="utf-8")
    out = tmp_path / "out"
    return ["--data-dir", str(data), "--snapshot", str(snap), "--out-dir", str(out)], out


ROOT = {"name": "Sales", "parent": None, "status": "Approved", "description": "d"}
GOOD = [ROOT, {"name": "Customer", "parent": "Sales", "status": "Approved", "description": "c",
               "objects": ["AdventureWorks2019.Sales.Customer"]}]


def test_check_returns_1_and_lists_errors_for_invalid_data(tmp_path, capsys):
    opts, _ = setup(tmp_path, [ROOT])  # Customer table unmapped
    assert build.main(["check", *opts]) == 1
    assert "AdventureWorks2019.Sales.Customer" in capsys.readouterr().out


def test_build_writes_nothing_when_invalid(tmp_path):
    opts, out = setup(tmp_path, [ROOT])
    assert build.main(["build", *opts]) == 1
    assert not out.exists() or not list(out.iterdir())


def test_build_writes_three_csvs_when_valid(tmp_path):
    opts, out = setup(tmp_path, GOOD)
    assert build.main(["build", *opts]) == 0
    assert sorted(p.name for p in out.iterdir()) == [
        "adventureworks-glossary.csv", "term-object-mapping.csv", "term-relationships.csv"]


def test_omd_error_prints_one_line_and_returns_2(tmp_path, monkeypatch, capsys):
    env = tmp_path / ".env"
    env.write_text("OMD_HOST=http://x/api\nOMD_TOKEN=secret-token\n", encoding="utf-8")

    def boom(_get_json):
        raise OmdError("OMD returned HTTP 401 for /v1/tables")

    monkeypatch.setattr(build, "fetch_snapshot", boom)
    code = build.main(["snapshot", "--env", str(env), "--snapshot", str(tmp_path / "s.json")])
    out = capsys.readouterr()
    assert code == 2
    assert out.err.strip() == "error: OMD returned HTTP 401 for /v1/tables"
    assert "secret-token" not in out.out + out.err


def _with_relationships(tmp_path, rels):
    opts, out = setup(tmp_path, GOOD)
    data = Path(opts[1])
    (data / "relationships.json").write_text(json.dumps(rels), encoding="utf-8")
    return opts, out


def test_check_rejects_curated_relationship_to_unknown_term(tmp_path, capsys):
    opts, _ = _with_relationships(tmp_path, [{"subject": "Sales.Customer", "relation": "buys", "object": "Sales.Ghost"}])
    assert build.main(["check", *opts]) == 1
    assert "Sales.Ghost" in capsys.readouterr().out


def test_build_expands_curated_relationship_paths_to_fqns(tmp_path):
    opts, out = _with_relationships(tmp_path, [
        {"subject": "Sales.Customer", "relation": "buys from", "object": "Sales", "evidence": "rule"}])
    assert build.main(["build", *opts]) == 0
    text = (out / "term-relationships.csv").read_text(encoding="utf-8")
    assert "AdventureWorks Business Glossary.Sales.Customer,buys from,AdventureWorks Business Glossary.Sales,rule,curated" in text
