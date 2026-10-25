"""CSV writers for the glossary upload, object mapping and term relationships."""
import csv
from pathlib import Path

from tools.glossary.model import GLOSSARY_NAME, Term, object_fqn

# OMD 2.0.5 rejects the import unless the header matches exactly, including the `name*` marker.
GLOSSARY_HEADER = ["parent", "name*", "displayName", "description", "synonyms", "relatedTerms",
                   "references", "tags", "reviewers", "owner", "glossaryStatus", "color",
                   "iconURL", "domains", "extension"]


def _write(path: Path, header: list[str], rows: list[list[str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def write_glossary_csv(terms: list[Term], path: Path, include_related: bool = True) -> None:
    ordered = sorted(terms, key=lambda t: t.parent is not None)  # stable: roots first
    # OMD's import fails ("Entity not found") when a row relates to a term updated earlier in the same file,
    # so each link is written once, on the earlier row; OMD mirrors it on the other term.
    position = {t.path: i for i, t in enumerate(ordered)}
    rows = []
    for i, t in enumerate(ordered):
        forward = [r for r in t.related if position[r["term"]] > i]
        related = ";".join(f"{r['type']}:{GLOSSARY_NAME}.{r['term']}" for r in forward) if include_related else ""
        parent = f"{GLOSSARY_NAME}.{t.parent}" if t.parent else ""
        rows.append([parent, t.name, t.name, t.description, ";".join(t.synonyms), related,
                     "", "", "", "", t.status, "", "", "", ""])
    _write(path, GLOSSARY_HEADER, rows)


def write_mapping_csv(terms: list[Term], path: Path, snapshot: dict | None = None) -> None:
    """Tables with no OMD description are marked `inferred`: the mapping is judgment, not documentation."""
    documented = set()
    if snapshot:
        prefix = snapshot["service"] + "."
        documented = {t["fullyQualifiedName"].removeprefix(prefix)
                      for tabs in snapshot["databases"].values() for t in tabs if t.get("description")}
    rows = []
    for t in terms:
        rows += [[t.fqn, "table", object_fqn(o), t.basis if not snapshot or o in documented else "inferred"]
                 for o in t.objects]
        rows += [[t.fqn, "column", object_fqn(c), t.basis] for c in t.columns]
    _write(path, ["term_fqn", "object_type", "object_fqn", "basis"], rows)


def derive_fk_relations(terms: list[Term], snapshot: dict) -> list[dict]:
    prefix = snapshot["service"] + "."
    by_table: dict[str, list[Term]] = {}
    for t in terms:
        for o in t.objects:
            by_table.setdefault(prefix + o, []).append(t)

    found: dict[tuple[str, str], dict] = {}
    for tables in snapshot["databases"].values():
        for table in tables:
            source = table["fullyQualifiedName"]
            for con in table.get("tableConstraints", []):
                if con.get("constraintType") != "FOREIGN_KEY":
                    continue
                for column, referred in zip(con["columns"], con["referredColumns"]):
                    target = referred.rsplit(".", 1)[0]
                    for s in by_table.get(source, []):
                        for o in by_table.get(target, []):
                            if s.fqn != o.fqn:
                                found.setdefault((s.fqn, o.fqn), {
                                    "subject": s.fqn, "relation": "references", "object": o.fqn,
                                    "evidence": f"fk: {source}.{column} -> {referred}"})
    return list(found.values())


def write_relationships_csv(curated: list[dict], derived: list[dict], path: Path) -> None:
    covered = {(r["subject"], r["object"]) for r in curated}
    rows = [[r["subject"], r["relation"], r["object"], r.get("evidence", ""), "curated"] for r in curated]
    rows += [[r["subject"], r["relation"], r["object"], r["evidence"], "fk"]
             for r in derived if (r["subject"], r["object"]) not in covered]
    _write(path, ["subject", "relation", "object", "evidence", "source"], rows)
