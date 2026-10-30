"""Data quality test cases and their latest results."""
import time
from urllib.parse import quote

from app.omd import OmdClient
from seed import definitions as d


def ensure_test(client: OmdClient, defn: d.TestDef) -> None:
    case = client.put("/dataQuality/testCases", {
        "name": defn.name,
        "entityLink": f"<#E::table::{defn.table}>",
        "testDefinition": defn.definition,
        "parameterValues": defn.parameters,
        "description": f"Demo check: {defn.name.replace('_', ' ')}",
    })
    client.post(f"/dataQuality/testCases/testCaseResults/{quote(case['fullyQualifiedName'], safe='')}", {
        "timestamp": int(time.time() * 1000),
        "testCaseStatus": defn.outcome,
        "result": "Seeded demo result",
    })
