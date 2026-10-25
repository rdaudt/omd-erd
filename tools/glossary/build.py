"""CLI: snapshot OMD metadata, check curated glossary data, build the output files."""
import argparse
import json
import sys
from pathlib import Path

from tools.glossary.model import load_exclusions, load_terms, validate
from tools.glossary.omd_client import OmdError, fetch_snapshot, load_env, make_get_json
from tools.glossary.writers import (
    derive_fk_relations,
    write_glossary_csv,
    write_mapping_csv,
    write_relationships_csv,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA = ROOT / "tools" / "glossary" / "data"
DEFAULT_SNAPSHOT = ROOT / "tools" / "glossary" / ".cache" / "snapshot.json"
DEFAULT_OUT = ROOT / "docs" / "glossary"


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tools.glossary.build")
    p.add_argument("command", choices=["snapshot", "check", "build"])
    p.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    p.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    p.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    p.add_argument("--env", type=Path, default=ROOT / ".env")
    p.add_argument("--schemas", help="comma-separated <db>.<schema> list limiting the coverage check")
    return p


def _snapshot(args) -> int:
    env = load_env(args.env)
    snap = fetch_snapshot(make_get_json(env["OMD_HOST"], env["OMD_TOKEN"]))
    args.snapshot.parent.mkdir(parents=True, exist_ok=True)
    args.snapshot.write_text(json.dumps(snap, indent=1), encoding="utf-8")
    counts = ", ".join(f"{db}: {len(t)} tables" for db, t in snap["databases"].items())
    print(f"snapshot saved to {args.snapshot} ({counts})")
    return 0


def _check(args) -> tuple[int, list, dict]:
    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    terms = load_terms(args.data_dir)
    schemas = set(args.schemas.split(",")) if args.schemas else None
    errors = validate(terms, snapshot, load_exclusions(args.data_dir), schemas)
    for e in errors:
        print(e)
    print(f"{len(terms)} terms, {len(errors)} errors")
    return (1 if errors else 0), terms, snapshot


def _build(args) -> int:
    code, terms, snapshot = _check(args)
    if code:
        return code
    rel_path = args.data_dir / "relationships.json"
    curated = json.loads(rel_path.read_text(encoding="utf-8")) if rel_path.exists() else []
    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_glossary_csv(terms, args.out_dir / "adventureworks-glossary.csv")
    write_mapping_csv(terms, args.out_dir / "term-object-mapping.csv")
    write_relationships_csv(curated, derive_fk_relations(terms, snapshot),
                            args.out_dir / "term-relationships.csv")
    print(f"wrote files to {args.out_dir}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "snapshot":
            return _snapshot(args)
        if args.command == "check":
            return _check(args)[0]
        return _build(args)
    except OmdError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
