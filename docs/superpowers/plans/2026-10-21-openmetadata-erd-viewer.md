# OpenMetadata ERD Viewer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a polished local read-only ERD viewer that discovers relational schemas through OpenMetadata 2.0.5 APIs and renders their tables, foreign keys, and rich catalog metadata on an interactive React canvas.

**Architecture:** A local FastAPI adapter owns OpenMetadata SDK access, JWT configuration, pagination, normalization, caching, and sample fallback. A React/TypeScript frontend consumes four fixed GET endpoints, lays out graph data with ELK.js, and renders ephemeral interactions with React Flow. OpenMetadata remains the source of truth and receives no writes.

**Tech Stack:** Python 3.12.10, FastAPI, Pydantic Settings, `openmetadata-ingestion==2.0.5.1`, pytest, React, TypeScript, Vite, React Flow (`@xyflow/react`), ELK.js, Vitest, Testing Library, Playwright.

## Global Constraints

- Target OpenMetadata server version is exactly `2.0.5`; use `openmetadata-ingestion==2.0.5.1`.
- Support live schemas containing up to 50 tables.
- Render declared foreign-key relationships only; do not infer relationships or display lineage.
- Keep the OpenMetadata URL and JWT in the backend environment; never include the JWT in frontend code or responses.
- Expose fixed read-only GET routes only; do not add a generic OpenMetadata proxy or any write route.
- Keep table positions, hidden state, collapse state, selection, and viewport state in browser memory only.
- Clearly label sample fallback data; never present it as live metadata.
- Preserve the selected midnight visual direction with violet accents and a right-side inspector.
- Existing `.env`, virtual environments, Docker compose file, setup notes, temporary files, and API test script are local inputs and must not be committed unless a task explicitly replaces them with sanitized project documentation.

## File structure

```text
backend/
  pyproject.toml                 # Backend dependencies and pytest configuration
  app/
    __init__.py
    main.py                      # FastAPI composition, CORS, and routes
    config.py                    # Environment-backed settings
    models.py                    # Stable public response models
    openmetadata_client.py       # SDK protocol and concrete read adapter
    catalog_service.py           # Hierarchy queries, pagination, normalization, cache/fallback
    sample_graph.json            # Bundled fallback graph
  tests/
    conftest.py                  # Shared fake SDK and app fixtures
    test_catalog_service.py      # Mapping, pagination, constraints, fallback
    test_api.py                  # HTTP contract and read-only route tests
frontend/
  package.json                   # Frontend scripts and dependencies
  vite.config.ts
  tsconfig.json
  index.html
  playwright.config.ts
  src/
    main.tsx                     # Browser entry point
    App.tsx                      # Application composition and selection flow
    styles.css                   # Midnight design tokens and application styling
    api/client.ts                # Typed calls to the FastAPI contract
    api/types.ts                 # Shared frontend API types
    components/CatalogSelector.tsx
    components/ErdCanvas.tsx
    components/TableNode.tsx
    components/RelationshipEdge.tsx
    components/InspectorPanel.tsx
    components/CanvasControls.tsx
    components/StatusBanner.tsx
    graph/layout.ts              # ELK conversion and layout
    graph/viewState.ts           # Pure visibility, collapse, and selection transforms
    test/setup.ts
    components/*.test.tsx
    graph/*.test.ts
  e2e/erd-viewer.spec.ts
scripts/
  dev.ps1                        # Starts backend and frontend locally
.env.example                     # Sanitized backend configuration template
README.md                        # Setup, operation, demo flow, and limitations
```

---

### Task 1: FastAPI foundation and stable response contract

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py`
- Create: `backend/app/models.py`
- Create: `backend/app/main.py`
- Create: `backend/tests/test_api.py`

**Interfaces:**
- Consumes: Environment variables `OMD_HOST`, `OMD_TOKEN`, optional `OMD_REQUEST_TIMEOUT_SECONDS`, and optional `OMD_CACHE_TTL_SECONDS`.
- Produces: `Settings`, Pydantic catalog/graph response models, and `create_app(catalog_service: CatalogServiceProtocol | None = None) -> FastAPI`.

- [ ] **Step 1: Add backend package metadata and a failing API contract test**

Create `backend/pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=78.1.1"]
build-backend = "setuptools.build_meta"

[project]
name = "omd-erd-backend"
version = "0.1.0"
requires-python = ">=3.12,<3.13"
dependencies = [
  "fastapi>=0.115,<1",
  "pydantic-settings>=2.10,<3",
  "uvicorn[standard]>=0.34,<1",
  "openmetadata-ingestion==2.0.5.1",
]

[project.optional-dependencies]
test = ["httpx>=0.28,<1", "pytest>=9,<10", "pytest-cov>=6,<8"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

Create `backend/tests/test_api.py`:

```python
from fastapi.testclient import TestClient

from app.main import create_app


class StubCatalogService:
    def list_services(self):
        return [{"id": "svc-1", "name": "MSSQL Desktop", "fullyQualifiedName": "MSSQL Desktop"}]


def test_services_contract_is_read_only():
    client = TestClient(create_app(StubCatalogService()))

    response = client.get("/api/services")

    assert response.status_code == 200
    assert response.json() == [
        {"id": "svc-1", "name": "MSSQL Desktop", "fullyQualifiedName": "MSSQL Desktop"}
    ]
    assert client.post("/api/services").status_code == 405
```

- [ ] **Step 2: Run the test and verify the missing application failure**

Run:

```powershell
rtk proxy .venv\Scripts\python.exe -m pip install -e ".\backend[test]"
rtk pytest backend/tests/test_api.py -v
```

Expected: FAIL during collection with `ModuleNotFoundError: No module named 'app'` or `No module named 'app.main'`.

- [ ] **Step 3: Implement settings, public models, and application factory**

Create `backend/app/config.py`:

```python
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    omd_host: str = Field(alias="OMD_HOST")
    omd_token: str = Field(alias="OMD_TOKEN")
    request_timeout_seconds: float = Field(10.0, alias="OMD_REQUEST_TIMEOUT_SECONDS")
    cache_ttl_seconds: int = Field(60, alias="OMD_CACHE_TTL_SECONDS")


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

Create `backend/app/models.py`:

```python
from typing import Literal

from pydantic import BaseModel, Field


class CatalogItem(BaseModel):
    id: str
    name: str
    fullyQualifiedName: str


class ColumnModel(BaseModel):
    name: str
    dataType: str
    nullable: bool
    primaryKey: bool = False
    foreignKey: bool = False
    description: str | None = None


class TableModel(BaseModel):
    id: str
    name: str
    fullyQualifiedName: str
    description: str | None = None
    owner: str | None = None
    tags: list[str] = Field(default_factory=list)
    tier: str | None = None
    columns: list[ColumnModel]


class RelationshipModel(BaseModel):
    id: str
    sourceTableId: str
    sourceColumn: str
    targetTableId: str
    targetColumn: str


class GraphResponse(BaseModel):
    source: Literal["live", "sample"]
    schema_: CatalogItem = Field(alias="schema")
    tables: list[TableModel]
    relationships: list[RelationshipModel]
    warnings: list[str] = Field(default_factory=list)

    model_config = {"populate_by_name": True}
```

The aliased `schema_` field serializes as `schema` without shadowing Pydantic APIs.

Create `backend/app/main.py`:

```python
from typing import Protocol

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.models import CatalogItem


class CatalogServiceProtocol(Protocol):
    def list_services(self) -> list[CatalogItem]:
        raise NotImplementedError


def create_app(catalog_service: CatalogServiceProtocol | None = None) -> FastAPI:
    app = FastAPI(title="OpenMetadata ERD Adapter", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_methods=["GET"],
        allow_headers=["Content-Type"],
    )

    @app.get("/api/services", response_model=list[CatalogItem])
    def list_services() -> list[CatalogItem]:
        if catalog_service is None:
            raise RuntimeError("Catalog service is not configured")
        return catalog_service.list_services()

    return app


app = create_app()
```

- [ ] **Step 4: Run the API test and dependency check**

Run:

```powershell
rtk pytest backend/tests/test_api.py -v
rtk proxy .venv\Scripts\python.exe -m pip check
```

Expected: `1 passed`; dependency check prints `No broken requirements found.`

- [ ] **Step 5: Commit the backend foundation**

```powershell
rtk git add backend
rtk git commit -m "feat: establish read-only backend contract"
```

---

### Task 2: OpenMetadata hierarchy adapter and pagination

**Files:**
- Create: `backend/app/openmetadata_client.py`
- Create: `backend/app/catalog_service.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_catalog_service.py`
- Modify: `backend/app/main.py`
- Modify: `backend/tests/test_api.py`

**Interfaces:**
- Consumes: `Settings` and OpenMetadata generated entity classes `DatabaseService`, `Database`, and `DatabaseSchema`.
- Produces: `OpenMetadataReader.list_entities(entity, fields, params)`, `CatalogService.list_services()`, `list_databases(service_id)`, and `list_schemas(database_id)`.

- [ ] **Step 1: Write failing hierarchy and pagination tests**

Create a fake SDK in `backend/tests/conftest.py` whose `list_entities` returns two pages with `paging.after`, and add tests like:

```python
def test_list_databases_filters_parent_and_follows_pagination(fake_reader):
    fake_reader.add_pages(
        "Database",
        [
            Page([entity("db-1", "Warehouse", service_id="svc-1")], after="next"),
            Page([entity("db-2", "Mart", service_id="svc-1")], after=None),
        ],
    )
    service = CatalogService(fake_reader, cache_ttl_seconds=60)

    result = service.list_databases("svc-1")

    assert [item.id for item in result] == ["db-2", "db-1"]
    assert fake_reader.calls[-1].params["after"] == "next"
    assert all(item.fullyQualifiedName for item in result)
```

Also test an unknown parent ID raises `CatalogNotFoundError` instead of returning unrelated children.

- [ ] **Step 2: Run the service tests and verify failure**

Run: `rtk pytest backend/tests/test_catalog_service.py -v`

Expected: FAIL because `app.catalog_service` and `CatalogService` do not exist.

- [ ] **Step 3: Implement the narrow SDK wrapper and hierarchy service**

In `backend/app/openmetadata_client.py`, build `OpenMetadataConnection` from `Settings`, initialize `OpenMetadata`, and expose only:

```python
class OpenMetadataReader:
    def list_entities(self, *, entity, fields: list[str], params: dict[str, str | int]):
        return self._client.list_entities(entity=entity, fields=fields, params=params)
```

In `backend/app/catalog_service.py`, implement one private paginator used by all hierarchy calls:

```python
def _all_entities(self, entity, *, fields: list[str], params: dict[str, str]) -> list[object]:
    items: list[object] = []
    after: str | None = None
    while True:
        page_params = {**params, "limit": 100}
        if after:
            page_params["after"] = after
        page = self._reader.list_entities(entity=entity, fields=fields, params=page_params)
        items.extend(page.entities)
        after = page.after
        if not after:
            return items
```

Map each SDK entity into `CatalogItem`, sort by case-insensitive name, and validate the selected parent exists before querying children. Use OpenMetadata's supported parent filter parameters rather than filtering a global collection in memory.

- [ ] **Step 4: Add hierarchy routes and HTTP validation tests**

Extend `create_app` with:

```python
@app.get("/api/databases", response_model=list[CatalogItem])
def list_databases(serviceId: str):
    return service.list_databases(serviceId)

@app.get("/api/schemas", response_model=list[CatalogItem])
def list_schemas(databaseId: str):
    return service.list_schemas(databaseId)
```

Register an exception handler that maps `CatalogNotFoundError` to HTTP 404 with `{"detail": "Catalog parent was not found"}`. Test missing query parameters return 422 and unknown parents return 404.

- [ ] **Step 5: Run hierarchy and API tests**

Run: `rtk pytest backend/tests/test_catalog_service.py backend/tests/test_api.py -v`

Expected: all hierarchy, pagination, sorting, and HTTP validation tests pass.

- [ ] **Step 6: Commit hierarchy discovery**

```powershell
rtk git add backend/app backend/tests
rtk git commit -m "feat: expose OpenMetadata catalog hierarchy"
```

---

### Task 3: Graph normalization, cache, and explicit fallback

**Files:**
- Create: `backend/app/sample_graph.json`
- Modify: `backend/app/models.py`
- Modify: `backend/app/catalog_service.py`
- Modify: `backend/app/main.py`
- Modify: `backend/tests/test_catalog_service.py`
- Modify: `backend/tests/test_api.py`

**Interfaces:**
- Consumes: OpenMetadata `Table` entities including `columns`, `tableConstraints`, `owners`, `tags`, and `tier` fields.
- Produces: `CatalogService.get_schema_graph(schema_id: str, refresh: bool = False) -> GraphResponse` and `GET /api/schemas/{schema_id}/graph?refresh=false`.

- [ ] **Step 1: Write failing normalization tests using realistic SDK-shaped fakes**

Add fixtures for two tables with a primary-key constraint and a foreign-key constraint. Assert:

```python
graph = service.get_schema_graph("schema-1")

assert graph.source == "live"
assert graph.tables[0].owner == "Data Architecture"
assert graph.tables[0].tier == "Tier1"
assert graph.tables[0].columns[0].primaryKey is True
assert graph.tables[1].columns[1].foreignKey is True
assert graph.relationships[0].model_dump() == {
    "id": "orders.customer_id->customer.id",
    "sourceTableId": "orders",
    "sourceColumn": "customer_id",
    "targetTableId": "customer",
    "targetColumn": "id",
}
```

Add tests proving malformed constraints are skipped with a warning, empty schemas stay live and empty, repeated calls hit the cache, `refresh=True` bypasses it, and SDK connectivity failure returns `source == "sample"`.

- [ ] **Step 2: Run the graph tests and verify failure**

Run: `rtk pytest backend/tests/test_catalog_service.py -k "graph or cache or fallback" -v`

Expected: FAIL because `get_schema_graph` and sample fallback do not exist.

- [ ] **Step 3: Implement deterministic normalization**

Implement focused helpers in `catalog_service.py`; keep generated-model shape handling inside these helpers:

```python
def _text(value: object | None) -> str | None:
    if value is None:
        return None
    return str(getattr(value, "root", value))


def _column_flags(table) -> tuple[set[str], set[str]]:
    primary_keys: set[str] = set()
    foreign_keys: set[str] = set()
    for constraint in table.tableConstraints or []:
        names = {_text(name) for name in constraint.columns or []}
        names.discard(None)
        constraint_type = _text(constraint.constraintType)
        if constraint_type == "PRIMARY_KEY":
            primary_keys.update(names)
        elif constraint_type == "FOREIGN_KEY":
            foreign_keys.update(names)
    return primary_keys, foreign_keys


def _map_column(column, primary_keys: set[str], foreign_keys: set[str]) -> ColumnModel:
    name = _text(column.name) or ""
    return ColumnModel(
        name=name,
        dataType=_text(column.dataType) or "UNKNOWN",
        nullable=bool(getattr(column, "nullable", True)),
        primaryKey=name in primary_keys,
        foreignKey=name in foreign_keys,
        description=_text(getattr(column, "description", None)),
    )


def _display_owner(table) -> str | None:
    owners = getattr(table, "owners", None) or []
    return _text(getattr(owners[0], "displayName", None) or getattr(owners[0], "name", None)) if owners else None


def _display_tags(table) -> tuple[list[str], str | None]:
    labels = sorted(filter(None, (_text(tag.tagFQN) for tag in (table.tags or []))))
    tier = next((label for label in labels if label.startswith("Tier.")), None)
    return [label for label in labels if label != tier], tier.removeprefix("Tier.") if tier else None
```

Implement `_map_relationships` by building a `{table fully-qualified name: table ID}` lookup, resolving each foreign-key constraint's local and referenced column pairs, and emitting one `RelationshipModel` per pair. Normalize fully qualified column references by matching the longest table FQN prefix before taking the remaining final segment as the column name. If either table or column cannot be resolved, append a warning and skip that pair. Sort tables by name and relationships by stable ID so tests and layouts are deterministic. Do not synthesize edges when constraints are absent.

- [ ] **Step 4: Add TTL cache and bundled sample graph**

Use an internal cache entry containing `expires_at` and `GraphResponse`. Cache only successful live results by schema ID. Load `sample_graph.json` with `GraphResponse.model_validate_json`; the sample must contain at least four related AdventureWorks-style tables and set `source` to `sample`.

Catch only connectivity, timeout, and upstream SDK errors for fallback. Validation bugs in application code must propagate during development rather than being hidden behind sample mode.

- [ ] **Step 5: Add graph route and response alias verification**

Add:

```python
@app.get("/api/schemas/{schema_id}/graph", response_model=GraphResponse, response_model_by_alias=True)
def get_graph(schema_id: str, refresh: bool = False):
    return service.get_schema_graph(schema_id, refresh=refresh)
```

Test the JSON key is exactly `schema`, sample responses include a warning, empty live responses do not fall back, and POST requests to `/api/services`, `/api/databases`, `/api/schemas`, and `/api/schemas/schema-1/graph` each return 405.

- [ ] **Step 6: Run the complete backend suite and verify coverage**

Run:

```powershell
rtk pytest backend/tests -v
rtk proxy .venv\Scripts\python.exe -m pytest backend/tests --cov=backend/app --cov-report=term-missing
```

Expected: all tests pass; the report shows the normalization and failure branches executed.

- [ ] **Step 7: Commit the graph adapter**

```powershell
rtk git add backend/app backend/tests
rtk git commit -m "feat: normalize OpenMetadata schemas into ERD graphs"
```

---

### Task 4: React shell, typed API client, and cascading catalog selector

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/api/types.ts`
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/components/CatalogSelector.tsx`
- Create: `frontend/src/components/StatusBanner.tsx`
- Create: `frontend/src/test/setup.ts`
- Create: `frontend/src/components/CatalogSelector.test.tsx`

**Interfaces:**
- Consumes: The four backend GET contracts from Tasks 1–3.
- Produces: `CatalogApi`, `CatalogSelectorProps`, `GraphResponse` TypeScript types, and `App` selection/load orchestration.

- [ ] **Step 1: Scaffold the testable Vite package and failing selector test**

Define scripts `dev`, `build`, `test`, `test:run`, and `lint` in `package.json`; add React, TypeScript, Vite, Vitest, jsdom, Testing Library, `@xyflow/react`, and `elkjs` dependencies.

Write a test that renders `CatalogSelector` with a fake `CatalogApi`, selects `MSSQL Desktop`, and asserts the database selector becomes enabled while the schema selector remains disabled. Then select a database and assert schemas load. Change the service and assert database/schema selections reset.

- [ ] **Step 2: Install dependencies and verify the selector test fails**

Run:

```powershell
rtk npm install --prefix frontend
rtk npm run test:run --prefix frontend -- CatalogSelector.test.tsx
```

Expected: FAIL because the API types and selector component do not exist.

- [ ] **Step 3: Implement exact shared frontend types and fetch client**

In `frontend/src/api/types.ts`, mirror the backend contract:

```ts
export type CatalogItem = { id: string; name: string; fullyQualifiedName: string };
export type ColumnModel = { name: string; dataType: string; nullable: boolean; primaryKey: boolean; foreignKey: boolean; description: string | null };
export type TableModel = { id: string; name: string; fullyQualifiedName: string; description: string | null; owner: string | null; tags: string[]; tier: string | null; columns: ColumnModel[] };
export type RelationshipModel = { id: string; sourceTableId: string; sourceColumn: string; targetTableId: string; targetColumn: string };
export type GraphResponse = { source: "live" | "sample"; schema: CatalogItem; tables: TableModel[]; relationships: RelationshipModel[]; warnings: string[] };
```

Implement `CatalogApi` with `listServices(signal)`, `listDatabases(serviceId, signal)`, `listSchemas(databaseId, signal)`, and `getGraph(schemaId, refresh, signal)`. A shared `getJson<T>` must throw an `ApiError` containing HTTP status and safe response detail.

- [ ] **Step 4: Implement selector cancellation and App orchestration**

`CatalogSelector` owns no graph state. It emits `{service, database, schema}` selection through callbacks and uses an `AbortController` per child request. `App` requests a graph only when a schema exists, discards stale results by aborting the previous request, and preserves the last successful graph until a new graph succeeds.

Render `StatusBanner` for loading, error, warning, and `source === "sample"`; sample mode copy must be exactly `Sample data — OpenMetadata unavailable`.

- [ ] **Step 5: Run selector tests, typecheck, and production build**

Run:

```powershell
rtk npm run test:run --prefix frontend -- CatalogSelector.test.tsx
rtk npm exec --prefix frontend tsc -- --noEmit
rtk npm run build --prefix frontend
```

Expected: selector tests pass, TypeScript exits 0, and Vite creates `frontend/dist`.

- [ ] **Step 6: Commit the frontend shell**

```powershell
rtk git add frontend
rtk git commit -m "feat: add typed catalog selection flow"
```

---

### Task 5: Pure graph state, ELK layout, and interactive ERD canvas

**Files:**
- Create: `frontend/src/graph/viewState.ts`
- Create: `frontend/src/graph/viewState.test.ts`
- Create: `frontend/src/graph/layout.ts`
- Create: `frontend/src/graph/layout.test.ts`
- Create: `frontend/src/components/ErdCanvas.tsx`
- Create: `frontend/src/components/TableNode.tsx`
- Create: `frontend/src/components/RelationshipEdge.tsx`
- Create: `frontend/src/components/CanvasControls.tsx`
- Create: `frontend/src/components/ErdCanvas.test.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `GraphResponse` and `TableModel` from Task 4.
- Produces: `layoutGraph(graph, collapsedIds) -> Promise<{nodes, edges}>`, pure rendered-node/edge selectors, and `ErdCanvasProps { graph, onSelectedTableChange }`.

- [ ] **Step 1: Write failing pure-state tests**

Test that `visibleGraph(graph, hiddenIds)` removes hidden tables and every incident edge; `relatedIds(graph, selectedId)` returns only direct neighbors; and `resetViewState()` returns empty hidden/collapsed sets and no selection.

- [ ] **Step 2: Run view-state tests and verify failure**

Run: `rtk npm run test:run --prefix frontend -- viewState.test.ts`

Expected: FAIL because `graph/viewState.ts` does not exist.

- [ ] **Step 3: Implement immutable graph-state helpers**

Implement named exports with `ReadonlySet<string>` inputs and new arrays/sets as outputs. Keep React Flow state out of this module so visibility, related-node highlighting, and schema reset behavior are deterministic unit-test targets.

- [ ] **Step 4: Write failing ELK layout tests**

Mock ELK and assert expanded node height is based on column count, collapsed node height is fixed, ports exist for edge endpoints, direction is left-to-right, and the returned React Flow edge preserves source/target column labels.

- [ ] **Step 5: Implement `layoutGraph` with stable dimensions and ports**

Configure ELK layered layout with `elk.direction: RIGHT`, orthogonal edge routing, spacing between nodes/layers, and stable node IDs. Use a Web Worker only if profiling shows main-thread layout is visibly blocking at 50 tables; otherwise keep the first version direct and simple.

- [ ] **Step 6: Write the failing canvas interaction test**

Mock React Flow and test: clicking a table selects it, collapsing it changes its accessible label, hiding it removes it and its edge, restore brings it back, schema identity change resets hidden/collapsed state, and `nodesConnectable={false}` prevents edit handles.

- [ ] **Step 7: Implement canvas components**

Use custom React Flow nodes and edges. `TableNode` renders PK/FK glyphs, type, and nullability; its header is the drag handle. `RelationshipEdge` uses a read-only smooth/step path with an accessible label such as `Orders.customer_id references Customer.id`. `CanvasControls` wraps React Flow controls and adds relayout, collapse/expand all, and restore-all actions.

After layout resolves, call `fitView({ padding: 0.15, duration: 350 })`. Preserve user positions until graph identity changes or the user explicitly chooses relayout.

- [ ] **Step 8: Run graph/canvas tests and build**

Run:

```powershell
rtk npm run test:run --prefix frontend -- viewState.test.ts layout.test.ts ErdCanvas.test.tsx
rtk npm exec --prefix frontend tsc -- --noEmit
rtk npm run build --prefix frontend
```

Expected: all graph and canvas tests pass; build exits 0.

- [ ] **Step 9: Commit the ERD canvas**

```powershell
rtk git add frontend/src
rtk git commit -m "feat: render interactive foreign-key ERDs"
```

---

### Task 6: Rich inspector and midnight presentation polish

**Files:**
- Create: `frontend/src/components/InspectorPanel.tsx`
- Create: `frontend/src/components/InspectorPanel.test.tsx`
- Create: `frontend/src/styles.css`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/ErdCanvas.tsx`
- Modify: `frontend/src/components/TableNode.tsx`
- Modify: `frontend/src/components/StatusBanner.tsx`

**Interfaces:**
- Consumes: Selected `TableModel`, graph relationships, hidden table IDs, and display actions.
- Produces: `InspectorPanelProps` with selection details, hidden-table restoration, global collapse/expand, relayout, and diagram counts.

- [ ] **Step 1: Write failing inspector behavior tests**

Assert the default inspector shows table/relationship counts and hidden-table restore controls. For a selected table, assert description, owner, tier, tags, columns, primary keys, incoming references, and outgoing references render. Assert missing optional values show `Not assigned` and not blank placeholders.

- [ ] **Step 2: Run inspector tests and verify failure**

Run: `rtk npm run test:run --prefix frontend -- InspectorPanel.test.tsx`

Expected: FAIL because `InspectorPanel` does not exist.

- [ ] **Step 3: Implement the two inspector modes**

Keep derivation pure: compute incoming/outgoing relationship lists from `graph.relationships`, resolve table names from an ID map, and pass callbacks down rather than importing canvas stores. The panel must remain mounted so its location is stable while content transitions.

- [ ] **Step 4: Apply the approved visual system**

Define CSS variables for charcoal surfaces, text contrast, borders, violet accents, warning/sample colors, shadows, spacing, and motion durations. Build a full-height shell with top selectors, central dot-grid canvas, and right inspector. Add visible keyboard focus states and `prefers-reduced-motion` overrides.

Use brief functional transitions only: 150–220 ms panel/content fades, table expansion, selection glow, and viewport motion. Do not add decorative animation or gradients that reduce diagram legibility.

- [ ] **Step 5: Add accessibility assertions and responsive laptop behavior**

Verify selector labels, canvas controls, table buttons, hide/restore actions, status banners, and edge labels are accessible by role/name. At narrower laptop widths, keep the canvas usable and allow the inspector to reduce width; no mobile-specific redesign is required.

- [ ] **Step 6: Run the complete frontend suite and build**

Run:

```powershell
rtk npm run test:run --prefix frontend
rtk npm exec --prefix frontend tsc -- --noEmit
rtk npm run build --prefix frontend
```

Expected: all frontend tests pass and the production build completes.

- [ ] **Step 7: Commit inspector and visual polish**

```powershell
rtk git add frontend/src
rtk git commit -m "feat: add rich metadata inspector and midnight theme"
```

---

### Task 7: Local operation, browser verification, and project documentation

**Files:**
- Create: `.env.example`
- Create: `scripts/dev.ps1`
- Create: `frontend/playwright.config.ts`
- Create: `frontend/e2e/erd-viewer.spec.ts`
- Create: `README.md`
- Modify: `frontend/package.json`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: Complete backend/frontend application and local OpenMetadata 2.0.5 stack.
- Produces: One-command local startup, an end-to-end test, a repeatable demo checklist, and contributor setup documentation.

- [ ] **Step 1: Add sanitized configuration and startup script**

Create `.env.example`:

```dotenv
OMD_HOST=http://localhost:8585/api
OMD_TOKEN=replace-with-a-bot-jwt
OMD_REQUEST_TIMEOUT_SECONDS=10
OMD_CACHE_TTL_SECONDS=60
```

Create `scripts/dev.ps1` that validates `.venv\Scripts\python.exe`, `frontend\node_modules`, `OMD_HOST`, and `OMD_TOKEN`, then starts Uvicorn on `127.0.0.1:8000` and Vite on `127.0.0.1:5173` as child processes. On Ctrl+C, stop both child processes in `finally` so no orphan development servers remain.

- [ ] **Step 2: Write the failing Playwright demo flow**

Add a `test:e2e` script and write a browser test that intercepts the four backend routes with deterministic fixtures, then:

```ts
await page.goto("/");
await page.getByLabel("Database service").selectOption("svc-1");
await page.getByLabel("Database").selectOption("db-1");
await page.getByLabel("Schema").selectOption("schema-1");
await expect(page.getByRole("group", { name: "Customer table" })).toBeVisible();
await page.getByRole("button", { name: "Collapse Customer" }).click();
await page.getByRole("button", { name: "Hide Customer" }).click();
await page.getByRole("button", { name: "Restore Customer" }).click();
await page.getByRole("group", { name: "Customer table" }).click();
await expect(page.getByRole("complementary")).toContainText("Data Architecture");
```

- [ ] **Step 3: Run the E2E test and correct only product/test-contract defects**

Run:

```powershell
rtk proxy npx --prefix frontend playwright install chromium
rtk npm run test:e2e --prefix frontend
```

Expected: one complete browser scenario passes. If it fails, preserve the accessible names documented above rather than weakening assertions to CSS selectors.

- [ ] **Step 4: Write setup and demo documentation**

Document prerequisites, Python 3.12.10 environment, backend editable install, frontend install, `.env` creation, Docker/OpenMetadata startup, `scripts/dev.ps1`, individual test commands, architecture summary, live/sample banner behavior, the 50-table boundary, and all explicit exclusions.

Include a five-minute demo script: start services, select a schema, explain the live API boundary, manipulate the canvas, select a table to show rich metadata, and demonstrate clearly labeled fallback mode.

- [ ] **Step 5: Run full automated verification**

Run:

```powershell
rtk pytest backend/tests -v
rtk proxy .venv\Scripts\python.exe -m pip check
rtk npm run test:run --prefix frontend
rtk npm exec --prefix frontend tsc -- --noEmit
rtk npm run build --prefix frontend
rtk npm run test:e2e --prefix frontend
```

Expected: all backend, frontend, type, build, and browser checks exit 0 with no failed tests.

- [ ] **Step 6: Perform the live OpenMetadata smoke test**

With the local OpenMetadata 2.0.5 Docker stack running and valid `.env` values, start `scripts/dev.ps1` and verify:

```text
Live data banner or neutral live status
Service → database → schema selection succeeds
Selected schema renders declared FK edges only
Drag, pan, zoom, fit, relayout, collapse, hide, and restore work
Inspector shows description, owner, tags/tier, columns, and relationships
Browser refresh resets the ephemeral layout
OpenMetadata entities remain unchanged
```

- [ ] **Step 7: Confirm tracked files contain no secrets**

Run:

```powershell
rtk git status --short
rtk grep "OMD_TOKEN=.+|eyJ[a-zA-Z0-9_-]+\.eyJ" .
```

Expected: `.env` and virtual environments are absent from status; secret scan returns no tracked credentials.

- [ ] **Step 8: Commit operational assets and documentation**

```powershell
rtk git add .env.example .gitignore README.md scripts frontend/playwright.config.ts frontend/e2e frontend/package.json
rtk git commit -m "docs: add local demo workflow and end-to-end verification"
```

---

## Final verification gate

- [ ] Run every command from Task 7 Step 5 on a clean working tree.
- [ ] Run the live smoke test from Task 7 Step 6 against OpenMetadata 2.0.5.
- [ ] Compare the delivered application line by line with `docs/superpowers/specs/2026-10-21-openmetadata-erd-viewer-design.md`.
- [ ] Confirm `rtk git status --short` contains only intentional local files and no secrets.
- [ ] Request code review before merging or presenting the finished branch.

