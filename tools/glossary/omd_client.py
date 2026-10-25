"""Read-only access to the OpenMetadata API for the glossary tooling."""
import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable

SERVICE = "MSSQL Desktop"
DATABASES = ("AdventureWorks2019", "AdventureWorksDW2019")
TABLE_FIELDS = "columns,description,tableConstraints"


class OmdError(Exception):
    """An OMD failure whose message is safe to print (never contains the token)."""


def load_env(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip("\"'")
    return values


def make_get_json(host: str, token: str) -> Callable[[str], dict]:
    def get_json(path: str) -> dict:
        request = urllib.request.Request(host + path, headers={"Authorization": f"Bearer {token}"})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            raise OmdError(f"OMD returned HTTP {exc.code} for {path.split('?')[0]}") from None
        except urllib.error.URLError as exc:
            raise OmdError(f"Cannot reach OMD at {host}: {exc.reason}") from None

    return get_json


def fetch_snapshot(get_json: Callable[[str], dict]) -> dict:
    databases = {}
    for db in DATABASES:
        tables, after = [], None
        while True:
            query = {"database": f"{SERVICE}.{db}", "limit": 100, "fields": TABLE_FIELDS}
            if after:
                query["after"] = after
            page = get_json("/v1/tables?" + urllib.parse.urlencode(query, quote_via=urllib.parse.quote))
            tables += page["data"]
            after = page.get("paging", {}).get("after")
            if not after:
                break
        databases[db] = tables
    return {"service": SERVICE, "databases": databases}


def dry_run_import(host: str, token: str, glossary: str, csv_text: str) -> dict:
    """Validate a glossary CSV against an existing glossary without importing it."""
    url = f"{host}/v1/glossaries/name/{urllib.parse.quote(glossary)}/import?dryRun=true"
    request = urllib.request.Request(
        url, data=csv_text.encode("utf-8"), method="PUT",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "text/plain"})
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise OmdError(f"OMD returned HTTP {exc.code} for the dry-run import") from None
    except urllib.error.URLError as exc:
        raise OmdError(f"Cannot reach OMD at {host}: {exc.reason}") from None
