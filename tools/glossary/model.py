"""Curated glossary terms: loading and validation against an OMD snapshot."""
import json
from dataclasses import dataclass, field
from pathlib import Path

GLOSSARY_NAME = "AdventureWorks Business Glossary"
SERVICE = "MSSQL Desktop"
OPERATIONAL_DB = "AdventureWorks2019"
RELATION_TYPES = ("relatedTo", "synonym", "broader", "narrower", "antonym", "partOf", "hasPart")
STATUSES = ("Approved", "Draft")


@dataclass
class Term:
    name: str
    parent: str | None
    status: str
    description: str
    synonyms: list[str] = field(default_factory=list)
    related: list[dict] = field(default_factory=list)
    objects: list[str] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)
    basis: str = "name"

    @property
    def path(self) -> str:
        return f"{self.parent}.{self.name}" if self.parent else self.name

    @property
    def fqn(self) -> str:
        return f"{GLOSSARY_NAME}.{self.path}"


def object_fqn(short: str) -> str:
    return f"{SERVICE}.{short}"


def load_terms(data_dir: Path) -> list[Term]:
    terms = []
    for path in sorted((data_dir / "terms").glob("*.json")):
        terms += [Term(**item) for item in json.loads(path.read_text(encoding="utf-8"))]
    return terms


def load_exclusions(data_dir: Path) -> dict[str, str]:
    return json.loads((data_dir / "exclusions.json").read_text(encoding="utf-8"))


def _snapshot_index(snapshot: dict) -> tuple[dict[str, set[str]], set[str]]:
    """Return ({short table name: column names}, all short table names)."""
    prefix = snapshot["service"] + "."
    tables = {}
    for tabs in snapshot["databases"].values():
        for t in tabs:
            short = t["fullyQualifiedName"].removeprefix(prefix)
            tables[short] = {c["name"] for c in t.get("columns", [])}
    return tables, set(tables)


def validate(terms, snapshot, exclusions, schemas=None) -> list[str]:
    errs = []
    tables, _ = _snapshot_index(snapshot)
    paths = [t.path for t in terms]
    path_set = set(paths)
    roots = {t.path for t in terms if t.parent is None}

    for p in sorted({p for p in paths if paths.count(p) > 1}):
        errs.append(f"duplicate term {p!r}")

    mapped = set()
    for t in terms:
        label = f"term {t.path!r}"
        if "." in t.name:
            errs.append(f"{label}: name contains a dot")
        if t.status not in STATUSES:
            errs.append(f"{label}: invalid status {t.status!r}")
        if t.parent is not None:
            if t.parent not in path_set:
                errs.append(f"{label}: parent {t.parent!r} does not exist")
            elif t.parent not in roots:
                errs.append(f"{label}: parent {t.parent!r} must be a root term")
            if not t.objects:
                errs.append(f"{label}: has no objects")
        if t.objects and t.status == "Approved" and not any(
            o.startswith(OPERATIONAL_DB + ".") for o in t.objects
        ):
            errs.append(f"{label}: warehouse-only terms must be Draft, not Approved")
        for o in t.objects:
            if o in tables:
                mapped.add(o)
            else:
                errs.append(f"{label}: object {o!r} not found in OMD snapshot")
        for c in t.columns:
            table_name, _, col = c.rpartition(".")
            if col not in tables.get(table_name, set()):
                errs.append(f"{label}: column {c!r} not found in OMD snapshot")
        for r in t.related:
            if r.get("type") not in RELATION_TYPES:
                errs.append(f"{label}: invalid related type {r.get('type')!r}")
            if r.get("term") not in path_set:
                errs.append(f"{label}: related term {r.get('term')!r} does not exist")

    for short in sorted(tables):
        in_scope = schemas is None or short.rsplit(".", 1)[0] in schemas
        if in_scope and short not in mapped and short not in exclusions:
            errs.append(f"table {short} is not mapped to any term or excluded")
    return errs
