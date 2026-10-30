"""Probe the local OMD instance for the capabilities the marketplace demo relies on."""
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]


def load_env() -> dict[str, str]:
    values = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip().strip("\"'")
    return values


def main() -> int:
    env = load_env()
    host = env["OMD_HOST"].rstrip("/")
    base = host + "/v1" if host.endswith("/api") else host + "/api/v1"
    client = httpx.Client(base_url=base, headers={"Authorization": f"Bearer {env['OMD_TOKEN']}"}, timeout=15)
    failures = 0

    def report(name: str, ok: bool, detail: str = "") -> None:
        nonlocal failures
        failures += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {name} {detail}")

    types = client.get("/metadata/types", params={"category": "entity", "limit": 100}).json().get("data", [])
    dp_type = next((t for t in types if t["name"] == "dataProduct"), None)
    if dp_type:
        prop = {"name": "probeTmp", "description": "probe", "propertyType": {"id": next(
            t["id"] for t in client.get("/metadata/types", params={"category": "field", "limit": 100}).json()["data"]
            if t["name"] == "string"), "type": "type"}}
        r = client.put(f"/metadata/types/{dp_type['id']}", json=prop)
        report("custom property on dataProduct", r.status_code in (200, 201), f"(HTTP {r.status_code})")
    else:
        report("custom property on dataProduct", False, "(dataProduct type not found)")

    r = client.get("/dataProducts", params={"limit": 1})
    report("dataProducts endpoint", r.status_code == 200, f"(HTTP {r.status_code})")

    r = client.get("/tags", params={"parent": "Certification", "limit": 10})
    names = [t["name"] for t in r.json().get("data", [])] if r.status_code == 200 else []
    report("certification tags", bool(names), f"({names})")

    r = client.get("/dataQuality/testCases", params={"limit": 1})
    report("test cases endpoint", r.status_code == 200, f"(HTTP {r.status_code})")

    t = client.get("/tables", params={"limit": 1}).json().get("data", [])
    if t:
        r = client.get(f"/lineage/table/name/{t[0]['fullyQualifiedName']}")
        report("lineage endpoint", r.status_code == 200, f"(HTTP {r.status_code})")
    else:
        report("lineage endpoint", False, "(no tables)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
