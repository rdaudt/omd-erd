import io
import json
from unittest import mock

import pytest

from tools.glossary.apply import execute, make_patch_json, plan, tag_label
from tools.glossary.omd_client import OmdError

T = "MSSQL Desktop.DB.dbo.Person"
TERM = "G.Domain.Person"


def row(object_fqn=T, object_type="table", basis="name", term=TERM):
    return {"term_fqn": term, "object_type": object_type, "object_fqn": object_fqn, "basis": basis}


def table(tags=(), column_tags=()):
    return {"id": "abc", "tags": [{"tagFQN": t} for t in tags],
            "columns": [{"fullyQualifiedName": f"{T}.Id", "tags": [{"tagFQN": t} for t in column_tags]}]}


def test_tag_label_is_derived_for_inferred_and_manual_otherwise():
    assert tag_label(TERM, "inferred")["labelType"] == "Derived"
    assert tag_label(TERM, "name")["labelType"] == "Manual"
    assert tag_label(TERM, "name")["source"] == "Glossary"


def test_plan_adds_table_and_column_tags_and_encodes_the_fqn():
    paths = []

    def get(path):
        paths.append(path)
        return table()

    patches, problems, skipped = plan([row(), row(f"{T}.Id", "column", "inferred")], get)

    assert paths == ["/v1/tables/name/MSSQL%20Desktop.DB.dbo.Person?fields=columns,tags"]
    ops = patches[T]["ops"]
    assert [o["path"] for o in ops] == ["/tags/-", "/columns/0/tags/-"]
    assert [o["value"]["labelType"] for o in ops] == ["Manual", "Derived"]
    assert (problems, skipped) == ([], 0)


def test_plan_skips_existing_and_duplicate_assignments():
    patches, _, skipped = plan([row(), row()], lambda p: table(tags=[TERM]))
    assert patches == {} and skipped == 2

    patches, _, skipped = plan([row(), row()], lambda p: table())
    assert len(patches[T]["ops"]) == 1 and skipped == 1


def test_plan_reports_missing_column_and_missing_table():
    _, problems, _ = plan([row(f"{T}.Nope", "column")], lambda p: table())
    assert problems == [f"{T}.Nope: column not found in OMD"]

    def gone(path):
        raise OmdError("OMD returned HTTP 404 for /v1/tables/name/x")

    patches, problems, _ = plan([row()], gone)
    assert patches == {} and "404" in problems[0]


def test_execute_patches_each_table_and_collects_failures():
    calls = []

    def patch(path, ops):
        calls.append((path, ops))
        if path.endswith("bad"):
            raise OmdError("HTTP 500")

    failures = execute({"a": {"id": "ok", "ops": [1]}, "b": {"id": "bad", "ops": [2]}}, patch)

    assert [c[0] for c in calls] == ["/v1/tables/ok", "/v1/tables/bad"]
    assert failures == ["b: HTTP 500"]


def test_make_patch_json_sends_json_patch_content_type():
    captured = {}

    class Resp:
        def __enter__(self):
            return io.BytesIO(b"{}")

        def __exit__(self, *a):
            return False

    def fake_urlopen(request, timeout=None):
        captured["request"] = request
        return Resp()

    with mock.patch("urllib.request.urlopen", fake_urlopen):
        make_patch_json("http://x/api", "tok")("/v1/tables/1", [{"op": "add"}])

    req = captured["request"]
    assert req.get_method() == "PATCH"
    assert req.get_header("Content-type") == "application/json-patch+json"
    assert json.loads(req.data) == [{"op": "add"}]


def test_make_patch_json_error_hides_token():
    import urllib.error
    err = urllib.error.HTTPError("http://x", 403, "Forbidden", {}, io.BytesIO(b""))
    with mock.patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(OmdError) as exc:
            make_patch_json("http://x/api", "secret-token")("/v1/tables/1", [])
    assert "secret-token" not in str(exc.value) and "403" in str(exc.value)
