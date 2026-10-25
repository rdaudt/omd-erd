import io
import urllib.error
from pathlib import Path
from unittest import mock

import pytest

from tools.glossary.omd_client import OmdError, fetch_snapshot, load_env, make_get_json


def test_load_env_parses_pairs_and_skips_comments(tmp_path: Path):
    env = tmp_path / ".env"
    env.write_text('# c\n\nOMD_HOST=http://x/api\nOMD_TOKEN="abc"\n', encoding="utf-8")
    assert load_env(env) == {"OMD_HOST": "http://x/api", "OMD_TOKEN": "abc"}


def test_fetch_snapshot_follows_paging():
    urls = []

    def table(name, db):
        return {"name": name, "fullyQualifiedName": f"MSSQL Desktop.{db}.s.{name}"}

    def fake_get(path):
        urls.append(path)
        if "AdventureWorksDW2019" in path:
            return {"data": [table("DimX", "AdventureWorksDW2019")], "paging": {}}
        if "after=p2" in path:
            return {"data": [table("B", "AdventureWorks2019")], "paging": {}}
        return {"data": [table("A", "AdventureWorks2019")], "paging": {"after": "p2"}}

    snap = fetch_snapshot(fake_get)

    assert snap["service"] == "MSSQL Desktop"
    assert [t["name"] for t in snap["databases"]["AdventureWorks2019"]] == ["A", "B"]
    assert [t["name"] for t in snap["databases"]["AdventureWorksDW2019"]] == ["DimX"]
    assert any("database=MSSQL%20Desktop.AdventureWorks2019" in u for u in urls)
    assert any("fields=columns%2Cdescription%2CtableConstraints" in u for u in urls)


def test_make_get_json_maps_401_to_omd_error_without_token():
    err = urllib.error.HTTPError("http://x", 401, "Unauthorized", {}, io.BytesIO(b""))
    get_json = make_get_json("http://x/api", "secret-token")
    with mock.patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(OmdError) as exc:
            get_json("/v1/tables")
    assert "secret-token" not in str(exc.value)
    assert "401" in str(exc.value)


def test_dry_run_import_sends_put_with_text_plain_and_dry_run_flag():
    from tools.glossary.omd_client import dry_run_import

    captured = {}

    class Resp:
        def __enter__(self):
            return io.BytesIO(b'{"status": "success", "numberOfRowsProcessed": 2}')

        def __exit__(self, *a):
            return False

    def fake_urlopen(request, timeout=None):
        captured["request"] = request
        return Resp()

    with mock.patch("urllib.request.urlopen", fake_urlopen):
        result = dry_run_import("http://x/api", "tok", "My Glossary", "name\nA\n")

    req = captured["request"]
    assert req.get_method() == "PUT"
    assert req.full_url == "http://x/api/v1/glossaries/name/My%20Glossary/import?dryRun=true"
    assert req.get_header("Content-type") == "text/plain"
    assert req.data == b"name\nA\n"
    assert result["numberOfRowsProcessed"] == 2
