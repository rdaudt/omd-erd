"""CLI: tag OMD tables and columns with glossary terms from term-object-mapping.csv.

Dry-run by default; pass --apply to write. This is the only module that writes to OMD.
"""
import argparse
import csv
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable

from tools.glossary.omd_client import OmdError, load_env, make_get_json

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MAPPING = ROOT / "docs" / "glossary" / "term-object-mapping.csv"

# `inferred` rows are judgment calls, so they are Derived (a steward can promote them); the rest are Manual.
LABEL_TYPE = {"inferred": "Derived"}


def make_patch_json(host: str, token: str) -> Callable[[str, list], dict]:
    def patch_json(path: str, ops: list) -> dict:
        request = urllib.request.Request(
            host + path, data=json.dumps(ops).encode("utf-8"), method="PATCH",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json-patch+json"})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            raise OmdError(f"OMD returned HTTP {exc.code} patching {path}") from None
        except urllib.error.URLError as exc:
            raise OmdError(f"Cannot reach OMD at {host}: {exc.reason}") from None
        except (OSError, ValueError):
            raise OmdError(f"Unreadable response from OMD patching {path}") from None

    return patch_json


def tag_label(term_fqn: str, basis: str) -> dict:
    return {"tagFQN": term_fqn, "source": "Glossary",
            "labelType": LABEL_TYPE.get(basis, "Manual"), "state": "Confirmed"}


def read_mapping(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _table_fqn(row: dict) -> str:
    return row["object_fqn"].rsplit(".", 1)[0] if row["object_type"] == "column" else row["object_fqn"]


def plan(rows: list[dict], get_json: Callable[[str], dict]) -> tuple[dict[str, dict], list[str], int]:
    """Return ({table_fqn: {"id", "ops"}}, problems, already_tagged_count). Reads only."""
    by_table: dict[str, list[dict]] = {}
    for row in rows:
        by_table.setdefault(_table_fqn(row), []).append(row)

    patches, problems, skipped = {}, [], 0
    for table_fqn, table_rows in by_table.items():
        path = f"/v1/tables/name/{urllib.parse.quote(table_fqn, safe='')}?fields=columns,tags"
        try:
            table = get_json(path)
        except OmdError as exc:
            problems.append(f"{table_fqn}: {exc}")
            continue
        columns = {c["fullyQualifiedName"]: (i, c) for i, c in enumerate(table.get("columns", []))}
        ops, seen = [], set()
        for row in table_rows:
            if row["object_type"] == "column":
                if row["object_fqn"] not in columns:
                    problems.append(f"{row['object_fqn']}: column not found in OMD")
                    continue
                index, column = columns[row["object_fqn"]]
                existing, op_path = column.get("tags") or [], f"/columns/{index}/tags/-"
            else:
                existing, op_path = table.get("tags") or [], "/tags/-"
            key = (op_path, row["term_fqn"])
            if key in seen or any(t.get("tagFQN") == row["term_fqn"] for t in existing):
                skipped += 1
                continue
            seen.add(key)
            ops.append({"op": "add", "path": op_path, "value": tag_label(row["term_fqn"], row["basis"])})
        if ops:
            patches[table_fqn] = {"id": table["id"], "ops": ops}
    return patches, problems, skipped


def execute(patches: dict[str, dict], patch_json: Callable[[str, list], dict]) -> list[str]:
    failures = []
    for table_fqn, patch in patches.items():
        try:
            patch_json(f"/v1/tables/{patch['id']}", patch["ops"])
        except OmdError as exc:
            failures.append(f"{table_fqn}: {exc}")
    return failures


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="tools.glossary.apply", description=__doc__)
    p.add_argument("--mapping", type=Path, default=DEFAULT_MAPPING)
    p.add_argument("--env", type=Path, default=ROOT / ".env")
    p.add_argument("--apply", action="store_true", help="write the tags (default is a dry run)")
    args = p.parse_args(argv)
    try:
        env = load_env(args.env)
        get_json = make_get_json(env["OMD_HOST"], env["OMD_TOKEN"])
        rows = read_mapping(args.mapping)
        patches, problems, skipped = plan(rows, get_json)
        adds = sum(len(x["ops"]) for x in patches.values())
        for problem in problems:
            print(f"problem: {problem}")
        print(f"{len(rows)} mapping rows: {adds} tags to add on {len(patches)} objects, "
              f"{skipped} already tagged, {len(problems)} problems")
        if not args.apply:
            print("dry run; pass --apply to write")
            return 1 if problems else 0
        if problems:
            print("not applying while there are problems", file=sys.stderr)
            return 1
        failures = execute(patches, make_patch_json(env["OMD_HOST"], env["OMD_TOKEN"]))
        for failure in failures:
            print(f"failed: {failure}", file=sys.stderr)
        print(f"applied {len(patches) - len(failures)} of {len(patches)} objects")
        return 1 if failures else 0
    except OmdError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyError as exc:
        print(f"error: missing setting or field {exc}", file=sys.stderr)
        return 2
    except (OSError, ValueError) as exc:
        print(f"error: {str(exc).splitlines()[0] if str(exc) else type(exc).__name__}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
