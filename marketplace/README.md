# Data Marketplace demo

A demo of an OpenMetadata-backed data marketplace: search curated data products, explore their metadata,
and request access. Submitting a request opens a **look-alike of the ServiceNow UI** in a new tab. There is
no real ServiceNow or Entra integration. It is separate from the ERD viewer (`backend/`, `frontend/`).

## Prerequisites

- OpenMetadata 2.0.5 running locally, and `OMD_HOST` / `OMD_TOKEN` set in the repo-root `.env`
  (the same values the ERD viewer uses).
- The repo-root `.venv` (Python 3.12) with `fastapi`, `httpx`, `pydantic-settings`, `uvicorn` installed.

## Seed the demo metadata (once, safe to re-run)

From `marketplace/`:

    ..\.venv\Scripts\python.exe -u -m seed.seed

It is additive and idempotent: it creates users, teams, domains, a `Sensitivity` classification, an
`entraGroup` custom property on data products, 7 data products (with owners, steward, certification,
sensitivity and Entra group), 56 data quality test cases with results, and lineage edges. It also adds
a domain to the tables used and descriptions to AdventureWorksDW tables that had none. It never
overwrites existing descriptions, tags or glossary terms. It takes a few minutes (OMD is slow at bulk
asset adds). Edit `seed/definitions.py` to change the products.

Note: OMD certification set through the API expires after 30 days; re-run the seed to refresh it.

## Run

    .\run.ps1            # http://localhost:8100/

## Demo script

1. Open `/`. Point at the natural-language box (placeholder only for now), then filter by domain,
   sensitivity, quality score, owner and certification, or search a keyword.
2. Open **Internet Sales Mart**: header badges, Overview, Datasets table, Quality, Glossary, Lineage.
3. Click **Request access**, enter a justification and duration, submit.
4. A new tab shows the ServiceNow-style request with the Entra group, read from the data product's
   `entraGroup` custom property in OpenMetadata.

## Tests

    ..\.venv\Scripts\python.exe -m pytest tests -q
    node --test "app/static/js/*.test.mjs"

## Layout

- `app/`: FastAPI service (OMD client, catalog shaping, access requests) and the static frontend
  (`app/static`: Bootstrap 5.3 + vanilla JS, vendored so the demo works offline).
- `seed/`: the idempotent OMD seed.
- `scripts/probe_omd.py`: checks the OMD capabilities the demo relies on.
