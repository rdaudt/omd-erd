# OpenMetadata ERD Viewer

A local, read-only schema explorer for OpenMetadata 2.0.5. Select a database service, database, and schema to explore declared foreign keys on a midnight React Flow canvas. The inspector shows descriptions, owners, tags, tiers, columns, and incoming/outgoing references.

## Prerequisites

- Windows with PowerShell 5.1 or newer.
- Python **3.12.10**, including `venv` and pip. The backend targets Python 3.12 and uses `openmetadata-ingestion==2.0.5.1`.
- Node.js **24 LTS** with npm (verified with Node 24.18.0).
- Docker Desktop and the existing OpenMetadata **2.0.5** compose stack, with catalog metadata ingested and a bot JWT allowed to read it.
- Free loopback ports **8000** and **5173**. OpenMetadata normally uses **8585**.
- `rtk` for the command examples below; it wraps commands without changing their behavior. `rtk proxy` is useful for Windows executables such as `npm.cmd`.

Run commands from this repository's application root. The existing Docker stack may live in a different checkout or directory.

## First-time setup

Create the exact Python environment and install the adapter in editable mode:

```powershell
rtk proxy py -3.12 -m venv .venv
rtk proxy .venv\Scripts\python.exe --version
# Confirm Python 3.12.10 before continuing.
rtk proxy .venv\Scripts\python.exe -m pip install -e "./backend[test]"
rtk proxy npm.cmd ci --prefix frontend
rtk proxy npx.cmd --prefix frontend playwright install chromium
rtk proxy powershell -NoProfile -Command "Copy-Item -LiteralPath .env.example -Destination .env"
```

Edit the ignored `.env` file locally. Use the values below, replacing only the bot JWT and, if necessary, the OpenMetadata API URL:

```dotenv
OMD_HOST=http://localhost:8585/api
OMD_TOKEN=replace-with-a-bot-jwt
OMD_REQUEST_TIMEOUT_SECONDS=10
OMD_CACHE_TTL_SECONDS=60
```

Keep the JWT in `.env` or the backend process environment. Never put it in a `VITE_*` variable, source file, URL, screenshot, or commit. Process environment values take precedence over `.env`. The startup script reads these four settings without executing their contents; use simple unquoted or fully quoted values without inline comments.

Start the **existing** OpenMetadata stack from its compose directory (for this laptop, `D:\Docker\openmetadata`):

```powershell
rtk proxy docker compose -f docker-compose-postgres.yml up -d
rtk proxy docker compose -f docker-compose-postgres.yml ps
```

Wait for the OpenMetadata server and its dependencies to be healthy. The catalog UI is at `http://localhost:8585`. This application does not ingest or create demo catalog entities.

## Run locally

From the application root:

```powershell
rtk proxy powershell -NoProfile -ExecutionPolicy Bypass -File scripts/dev.ps1
```

Open **http://127.0.0.1:5173**. The script checks the environment, dependencies, API URL, and port availability; starts Uvicorn on `127.0.0.1:8000` and Vite on `127.0.0.1:5173`; and writes local logs under ignored `.dev-logs/`. Cold backend startup can take a minute while the OpenMetadata SDK imports. Press **Ctrl+C in the launching terminal** to stop both owned process trees. If either server exits, the script stops the other in `finally`. Close the servers before running E2E tests because Playwright owns port 5173.

For separate terminals, activate the environment in each backend terminal or let Pydantic read the root `.env`:

```powershell
# Terminal 1, application root
rtk proxy .venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000

# Terminal 2, application root
rtk proxy npm.cmd run dev --prefix frontend -- --host 127.0.0.1 --port 5173 --strictPort
```

Vite proxies `/api` to the local adapter. The browser never receives the OpenMetadata JWT or calls OpenMetadata directly.

## Using the viewer

1. Choose **Database service → Database → Schema**. Use a schema with **up to 50 tables** for the supported demo boundary. Larger schemas have no readability or performance guarantee; they are not truncated silently.
2. Wait for **Laying out diagram…** to finish. ELK downloads on the first graph request and places tables automatically.
3. Drag the blank area of a table header to move it. Drag empty canvas to pan; use the wheel or **Zoom In**, **Zoom Out**, and **Fit View** controls to navigate.
4. Collapse/expand or hide individual tables with their header buttons. **Collapse all tables**, **Expand all tables**, **Relayout diagram**, and restore actions are also available. Hiding a table hides its connected edges. The inspector lists hidden tables for individual restoration.
5. Select a table or its name to see metadata and immediate relationships. Column labels and arrowheads point from the referencing FK column toward the referenced column. Unrelated elements dim. Clear selection by clicking the canvas.

Positions, collapse state, hidden tables, selection, and viewport exist only in browser memory. Schema changes and browser refresh reset that state. Relayout resets positions while retaining visibility and collapse choices. No diagram interaction writes to OpenMetadata.

Successful live data has a neutral status (no sample banner). A graph request that cannot reach OpenMetadata returns a bundled graph with a persistent **Sample data — OpenMetadata unavailable** banner and an explanatory warning. Missing metadata displays **Not assigned**. Invalid or unresolved FK constraints are skipped with warnings. An empty live schema remains empty. Initial service/database/schema discovery still requires live connectivity; fallback is at the graph boundary and does not fabricate a catalog hierarchy.

The adapter caches successful graph responses for 60 seconds by default. `GET /api/schemas/{schemaId}/graph?refresh=true` bypasses the in-process graph cache. Browser refresh clears view state but may reuse a cached graph response.

## Five-minute demo

- **0:00–0:45 — Start.** Confirm the Docker stack is healthy, run `scripts/dev.ps1`, and open the viewer. Introduce the local adapter/API boundary and the server-only JWT.
- **0:45–1:30 — Discover.** Select the service, database, and a useful schema with declared foreign keys. Explain that these are live catalog entities read through the version-matched SDK; neutral status indicates live data.
- **1:30–2:45 — Explore.** Drag a table, pan, zoom, fit, and relayout. Collapse one/all tables, expand, hide a connected table, and restore it from the inspector. Explain that only declared same-schema FKs produce edges.
- **2:45–3:45 — Inspect.** Select a table. Walk through its description, owner, tags/tier, column types, nullability, PK/FK badges, and incoming/outgoing references. Explain absent optional metadata and non-blocking constraint warnings.
- **3:45–4:15 — Reset.** Refresh the page, reselect the schema, and show that layout/display changes were temporary.
- **4:15–5:00 — Fallback.** Run the deterministic browser scenario below to demonstrate the clearly labeled sample UI. For a real transport-failure demonstration, use the separate-terminal workflow: populate the selectors while live, stop only the adapter, temporarily set its `OMD_HOST` to `http://127.0.0.1:9/api` in that terminal, restart the adapter, and select the already populated schema. The frontend stays open. Show the sample banner, then stop the adapter, remove that temporary environment override, and restart with the valid `.env`. Keep the Docker catalog running and unchanged. Do not reload the frontend until live connectivity is restored.

The deterministic E2E test intercepts exactly the adapter's four routes with fixtures. It demonstrates UI behavior independently of Docker; it does not prove live connectivity. Run a live smoke check before a presentation.

## Verification

Use the project virtual environment for backend checks:

```powershell
rtk proxy .venv\Scripts\python.exe -m pytest backend/tests -v
rtk proxy .venv\Scripts\python.exe -m pip check
rtk proxy npm.cmd run test:run --prefix frontend
rtk proxy npm.cmd exec --prefix frontend tsc -- --noEmit --project frontend/tsconfig.json
rtk proxy npm.cmd run build --prefix frontend
rtk proxy npm.cmd run test:e2e --prefix frontend
```

The browser test starts and stops its own Vite server, uses Chromium, and covers catalog cascading, a real table drag, collapse/expand, hidden-edge removal and restoration, zoom/fit/relayout, rich metadata, ephemeral refresh state, read-only requests, and sample labeling. Failure screenshots and traces are ignored under `frontend/test-results/`; inspect a trace with `rtk proxy npx.cmd --prefix frontend playwright show-trace <trace.zip>`.

For live verification, use the actual Docker catalog, confirm the neutral live status, check the expected declared edges against the source constraints, exercise every canvas control, inspect metadata, and verify refresh reset. The app has no catalog write route. Check the worktree before committing and scan tracked files without printing any matching secret values:

```powershell
rtk git status --short
rtk git grep -l -E "eyJ[a-zA-Z0-9_-]+\\.eyJ" -- .
```

## Architecture and boundaries

`frontend/` is React/TypeScript with React Flow for the graph, lazy-loaded ELK for layered layout, and in-memory view state. `backend/` is FastAPI/Pydantic with the OpenMetadata Python SDK, pagination, normalized graph mapping, bounded request timeouts, graph caching, and a bundled fallback. OpenMetadata 2.0.5 remains the live source of truth.

The adapter exposes fixed read-only catalog operations:

| Route | Purpose |
| --- | --- |
| `GET /api/services` | Database services |
| `GET /api/databases?serviceId=…` | Databases under a validated service |
| `GET /api/schemas?databaseId=…` | Schemas under a validated database |
| `GET /api/schemas/{schemaId}/graph` | Complete normalized graph; optional `refresh=true` |

There is no arbitrary-path proxy and no OpenMetadata write operation. Both development servers bind to loopback. This is a laptop demo, with no application authentication screens or application-level authorization.

Explicit exclusions: metadata/relationship editing; saved or shareable layouts; image, PDF, or model export; authentication screens/application-level authorization; lineage or inferred relationships; cross-schema edges; collaboration or multi-user state; production deployment; mobile-specific design; and rendering guarantees beyond 50 tables.

See the [design specification](docs/superpowers/specs/2026-10-21-openmetadata-erd-viewer-design.md) for the full contract.
