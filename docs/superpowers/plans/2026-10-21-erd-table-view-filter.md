# ERD Table and View Filter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users render tables only, views only, or both in an ERD, with tables selected by default.

**Architecture:** The backend continues returning one complete schema graph and adds a normalized `entityType` discriminator to every `TableModel`. The frontend owns a display-mode preference and derives a filtered graph before rendering; this keeps mode changes local and immediate while ensuring relationships survive only when both endpoints are included. Manual hiding remains independent inside `ErdCanvas`, while a mode change remounts the canvas to guarantee a fresh layout and fit for the newly visible entity set.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, `openmetadata-ingestion==2.0.5.1`, React 19, TypeScript 7, React Flow, ELK.js, pytest, Vitest/Testing Library, Playwright.

## Global Constraints

- The default display mode is `tables` on every fresh application load.
- View types are OpenMetadata `View`, `SecureView`, and `MaterializedView`; every other known, missing, or future table type is classified as `table` so existing entities never disappear unexpectedly.
- Display-mode filtering is client-side and must not add query parameters or duplicate backend cache entries.
- A relationship renders only when both endpoint entities are in the selected display mode.
- Display-mode filtering must not add IDs to `hiddenTableIds`; category filtering and explicit user hiding are separate state.
- Switching display mode clears selection and resets the canvas layout, collapse, manual-hide, pan, and zoom state for the newly selected entity set.
- Existing API field name `tables` and component/type names such as `TableModel` remain unchanged to avoid an unrelated contract-wide rename.
- The application remains read-only and adds no OpenMetadata write operations.

---

## File structure

- Modify `backend/app/models.py`: add the normalized entity discriminator to the graph contract.
- Modify `backend/app/catalog_service.py`: request and classify OpenMetadata `tableType`.
- Modify `backend/app/sample_graph.json`: make fallback graph entities conform to the contract and include a representative view.
- Modify `backend/tests/test_catalog_service.py`: cover normalization and SDK field requests.
- Modify `frontend/src/api/types.ts`: mirror the contract and define the display-mode type.
- Create `frontend/src/graph/entityFilter.ts`: own pure entity/relationship filtering and mode-specific labels/counts.
- Create `frontend/src/graph/entityFilter.test.ts`: exhaustively test the pure filtering rules.
- Modify `frontend/src/App.tsx`: own the user preference, derive the rendered graph, render accurate counts/empty states, and reset canvas state on mode changes.
- Modify `frontend/src/App.test.tsx`: verify default mode, mode switching, selection reset, filtered relationships, empty states, and schema behavior.
- Modify `frontend/src/components/InspectorPanel.tsx`: expose an accessible mode selector and use entity-neutral display copy.
- Modify `frontend/src/components/InspectorPanel.test.tsx`: verify selector behavior and counts.
- Modify `frontend/src/components/ErdCanvas.tsx`: generalize user-facing labels from tables to entities where they cover both types.
- Modify `frontend/src/components/TableNode.tsx`: expose whether a rendered card is a table or view in visible and accessible text.
- Modify `frontend/src/components/ErdCanvas.test.tsx`: update fixtures and verify view-card labeling.
- Modify `frontend/src/styles.css`: style the selector and view badge.
- Modify `frontend/e2e/erd-viewer.spec.ts`: exercise tables, views, and both against a mixed fixture.
- Modify `docs/superpowers/specs/2026-10-21-openmetadata-erd-viewer-design.md`: record the extended contract and interaction.

---

### Task 1: Normalize OpenMetadata entity types in the backend graph

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/catalog_service.py`
- Test: `backend/tests/test_catalog_service.py`

**Interfaces:**
- Consumes: OpenMetadata `Table.tableType`, whose string representation is obtained through the existing `_text` helper.
- Produces: `TableModel.entityType: Literal["table", "view"]` and `_entity_type(table: object) -> Literal["table", "view"]`.

- [ ] **Step 1: Extend backend fixtures and write failing classification tests**

Update `graph_table` so tests can describe the SDK field without repeating setup:

```python
def graph_table(
    table_id: str,
    name: str,
    fqn: str,
    columns,
    constraints=None,
    *,
    owners=None,
    tags=None,
    table_type=None,
):
    table = entity(table_id, name, fqn)
    table.columns = columns
    table.tableConstraints = constraints
    table.description = None
    table.owners = SimpleNamespace(root=owners or [])
    table.tags = tags or []
    table.tableType = table_type
    return table
```

Add these tests:

```python
@pytest.mark.parametrize("table_type", ["View", "SecureView", "MaterializedView"])
def test_graph_classifies_openmetadata_view_types(fake_reader, table_type):
    add_graph_schema(fake_reader, [
        graph_table("report", "report", "svc.db.dbo.report", [], table_type=table_type),
    ])

    graph = CatalogService(fake_reader, cache_ttl_seconds=60).get_schema_graph("schema-1")

    assert graph.tables[0].entityType == "view"


@pytest.mark.parametrize("table_type", ["Regular", "External", "Iceberg", "Dynamic", None, "FutureType"])
def test_graph_classifies_other_and_missing_types_as_tables(fake_reader, table_type):
    add_graph_schema(fake_reader, [
        graph_table("orders", "orders", "svc.db.dbo.orders", [], table_type=table_type),
    ])

    graph = CatalogService(fake_reader, cache_ttl_seconds=60).get_schema_graph("schema-1")

    assert graph.tables[0].entityType == "table"
```

In `test_graph_normalizes_sdk_shaped_tables_and_foreign_keys`, also assert:

```python
assert graph.tables[0].entityType == "table"
assert fake_reader.calls[1].fields == ["columns", "tableConstraints", "owners", "tags", "tableType"]
```

- [ ] **Step 2: Run the focused backend tests and confirm failure**

Run from `backend`:

```powershell
rtk pytest tests/test_catalog_service.py -q
```

Expected: failures report that `TableModel` has no `entityType`, and the requested fields omit `tableType`.

- [ ] **Step 3: Add the normalized backend contract and classifier**

In `backend/app/models.py`, import and add:

```python
from typing import Literal

class TableModel(BaseModel):
    id: str
    name: str
    fullyQualifiedName: str
    entityType: Literal["table", "view"]
    description: str | None = None
    owner: str | None = None
    tags: list[str] = Field(default_factory=list)
    tier: str | None = None
    columns: list[ColumnModel]
```

In `backend/app/catalog_service.py`, add the classifier near the other mapping helpers:

```python
VIEW_TABLE_TYPES = {"View", "SecureView", "MaterializedView"}


def _entity_type(table: object) -> Literal["table", "view"]:
    return "view" if _text(getattr(table, "tableType", None)) in VIEW_TABLE_TYPES else "table"
```

Import `Literal`, request the field, and map it:

```python
tables = self._all_entities(
    Table,
    fields=["columns", "tableConstraints", "owners", "tags", "tableType"],
    params={"databaseSchema": model_str(schema.fullyQualifiedName)},
)
```

```python
mapped_tables.append(TableModel(
    id=_text(table.id) or "",
    name=_text(table.name) or "",
    fullyQualifiedName=_text(table.fullyQualifiedName) or "",
    entityType=_entity_type(table),
    description=_text(getattr(table, "description", None)),
    owner=_display_owner(table),
    tags=tags,
    tier=tier,
    columns=[_map_column(column, primary_keys, foreign_keys) for column in table.columns or []],
))
```

- [ ] **Step 4: Run backend tests**

Run from `backend`:

```powershell
rtk pytest tests/test_catalog_service.py -q
rtk pytest -q
```

Expected: all backend tests pass.

- [ ] **Step 5: Commit the backend contract**

```powershell
rtk git add backend/app/models.py backend/app/catalog_service.py backend/tests/test_catalog_service.py
rtk git commit -m "feat: classify ERD tables and views"
```

---

### Task 2: Add the frontend contract and pure graph filter

**Files:**
- Modify: `frontend/src/api/types.ts`
- Create: `frontend/src/graph/entityFilter.ts`
- Create: `frontend/src/graph/entityFilter.test.ts`

**Interfaces:**
- Consumes: `TableModel.entityType` from Task 1.
- Produces: `EntityDisplayMode`, `filterGraph(graph, mode)`, `entityCounts(graph)`, and `emptyMessage(mode)`.

- [ ] **Step 1: Add the frontend type and failing pure-function tests**

In `frontend/src/api/types.ts`, add:

```ts
export type EntityType = 'table' | 'view';
export type EntityDisplayMode = 'tables' | 'views' | 'both';
```

Add `entityType: EntityType` to `TableModel`.

Create `frontend/src/graph/entityFilter.test.ts` with a mixed graph containing `orders` (`table`), `customers` (`table`), and `order_summary` (`view`), plus table-table and table-view relationships. Test these exact outcomes:

```ts
expect(filterGraph(graph, 'tables').tables.map(({ id }) => id)).toEqual(['orders', 'customers']);
expect(filterGraph(graph, 'tables').relationships.map(({ id }) => id)).toEqual(['orders-customers']);
expect(filterGraph(graph, 'views').tables.map(({ id }) => id)).toEqual(['order_summary']);
expect(filterGraph(graph, 'views').relationships).toEqual([]);
expect(filterGraph(graph, 'both')).toEqual(graph);
expect(entityCounts(graph)).toEqual({ tables: 2, views: 1 });
expect(emptyMessage('tables')).toBe('No tables in this schema.');
expect(emptyMessage('views')).toBe('No views in this schema.');
expect(emptyMessage('both')).toBe('No tables or views in this schema.');
```

- [ ] **Step 2: Run the new test and confirm failure**

Run from `frontend`:

```powershell
rtk npm run test:run -- src/graph/entityFilter.test.ts
```

Expected: FAIL because `entityFilter.ts` does not exist.

- [ ] **Step 3: Implement the pure filtering module**

Create `frontend/src/graph/entityFilter.ts`:

```ts
import type { EntityDisplayMode, GraphResponse } from '../api/types';

export function filterGraph(graph: GraphResponse, mode: EntityDisplayMode): GraphResponse {
  if (mode === 'both') return graph;
  const entityType = mode === 'tables' ? 'table' : 'view';
  const tables = graph.tables.filter((table) => table.entityType === entityType);
  const includedIds = new Set(tables.map((table) => table.id));
  return {
    ...graph,
    tables,
    relationships: graph.relationships.filter(
      (edge) => includedIds.has(edge.sourceTableId) && includedIds.has(edge.targetTableId),
    ),
  };
}

export function entityCounts(graph: GraphResponse): { tables: number; views: number } {
  return {
    tables: graph.tables.filter((entity) => entity.entityType === 'table').length,
    views: graph.tables.filter((entity) => entity.entityType === 'view').length,
  };
}

export function emptyMessage(mode: EntityDisplayMode): string {
  if (mode === 'tables') return 'No tables in this schema.';
  if (mode === 'views') return 'No views in this schema.';
  return 'No tables or views in this schema.';
}
```

- [ ] **Step 4: Run the graph unit tests**

```powershell
rtk npm run test:run -- src/graph/entityFilter.test.ts src/graph/layout.test.ts src/graph/viewState.test.ts
```

Expected: all selected tests pass after adding `entityType: 'table'` to existing graph fixtures reported by TypeScript.

- [ ] **Step 5: Commit the frontend graph primitive**

```powershell
rtk git add frontend/src/api/types.ts frontend/src/graph/entityFilter.ts frontend/src/graph/entityFilter.test.ts frontend/src/graph/layout.test.ts frontend/src/graph/viewState.test.ts
rtk git commit -m "feat: filter ERD graph by entity type"
```

---

### Task 3: Add the accessible display-mode selector

**Files:**
- Modify: `frontend/src/components/InspectorPanel.tsx`
- Modify: `frontend/src/components/InspectorPanel.test.tsx`
- Modify: `frontend/src/styles.css`

**Interfaces:**
- Consumes: `EntityDisplayMode` from Task 2 and the complete unfiltered `graph` for table/view totals.
- Produces: `InspectorPanelProps.displayMode` and `InspectorPanelProps.onDisplayModeChange(mode)`.

- [ ] **Step 1: Write failing inspector tests**

Extend the fixture with `entityType` values, including at least one view. Extend `props()` with:

```ts
displayMode: 'tables',
onDisplayModeChange: vi.fn(),
```

Add a test that renders the overview, verifies `Tables` is checked by default, clicks `Views`, and expects:

```ts
const group = within(panel).getByRole('radiogroup', { name: 'Entities to display' });
expect(within(group).getByRole('radio', { name: 'Tables' })).toBeChecked();
await user.click(within(group).getByRole('radio', { name: 'Views' }));
expect(actions.onDisplayModeChange).toHaveBeenCalledWith('views');
expect(within(panel).getByText('2 tables')).toBeInTheDocument();
expect(within(panel).getByText('1 view')).toBeInTheDocument();
```

- [ ] **Step 2: Run the inspector test and confirm failure**

```powershell
rtk npm run test:run -- src/components/InspectorPanel.test.tsx
```

Expected: FAIL because the new props and radio group do not exist.

- [ ] **Step 3: Implement the selector and neutral display copy**

Add these props:

```ts
displayMode: EntityDisplayMode;
onDisplayModeChange: (mode: EntityDisplayMode) => void;
```

In the overview Display section, render:

```tsx
<fieldset className="entity-mode" aria-label="Entities to display">
  <legend>Show</legend>
  {([
    ['tables', 'Tables'],
    ['views', 'Views'],
    ['both', 'Both'],
  ] as const).map(([value, label]) => (
    <label key={value}>
      <input
        type="radio"
        name="entity-display-mode"
        value={value}
        checked={displayMode === value}
        onChange={() => onDisplayModeChange(value)}
      />
      <span>{label}</span>
    </label>
  ))}
</fieldset>
```

Use `entityCounts(graph)` to show separate table and view totals. Change overview-only copy to “Select an entity…” and hidden-section copy to “Hidden entities” / “All entities are visible.” Keep existing button accessible names for collapse/expand/restore until Task 4 updates all canvas-facing terminology together.

Add focused styles:

```css
.entity-mode { margin: 0 0 var(--space-3); padding: 0; border: 0; }
.entity-mode legend { margin-bottom: var(--space-2); color: var(--text-muted); font-size: 12px; }
.entity-mode { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--space-1); }
.entity-mode legend { grid-column: 1 / -1; }
.entity-mode input { position: absolute; opacity: 0; pointer-events: none; }
.entity-mode span { display: block; padding: 7px 8px; border: 1px solid var(--border); border-radius: 6px; text-align: center; cursor: pointer; }
.entity-mode input:checked + span { border-color: var(--accent); color: var(--text); background: var(--surface-raised); }
.entity-mode input:focus-visible + span { outline: 2px solid var(--accent); outline-offset: 2px; }
```

- [ ] **Step 4: Run the inspector tests**

```powershell
rtk npm run test:run -- src/components/InspectorPanel.test.tsx
```

Expected: all inspector tests pass.

- [ ] **Step 5: Commit the selector**

```powershell
rtk git add frontend/src/components/InspectorPanel.tsx frontend/src/components/InspectorPanel.test.tsx frontend/src/styles.css
rtk git commit -m "feat: add ERD entity display selector"
```

---

### Task 4: Integrate filtering and reset semantics in the application

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/App.test.tsx`
- Modify: `frontend/src/components/ErdCanvas.tsx`
- Modify: `frontend/src/components/ErdCanvas.test.tsx`

**Interfaces:**
- Consumes: `filterGraph`, `emptyMessage`, `EntityDisplayMode`, and Task 3 inspector props.
- Produces: a filtered `renderedGraph` passed consistently to `ErdCanvas`; the inspector receives the complete graph for totals and the filtered selected entity/display state.

- [ ] **Step 1: Write failing application integration tests**

Update every frontend `TableModel` fixture with `entityType: 'table'` unless it intentionally represents a view. Make the `App.test.tsx` mock canvas render entity IDs and relationship IDs from its `graph` prop.

Add a mixed graph test that verifies:

```ts
expect(screen.getByLabelText('Rendered entities')).toHaveTextContent('orders,customers');
expect(screen.getByLabelText('Rendered relationships')).toHaveTextContent('orders-customers');

await user.click(screen.getByRole('radio', { name: 'Views' }));
expect(screen.getByLabelText('Rendered entities')).toHaveTextContent('order-summary');
expect(screen.getByLabelText('Rendered relationships')).toBeEmptyDOMElement();

await user.click(screen.getByRole('radio', { name: 'Both' }));
expect(screen.getByLabelText('Rendered entities')).toHaveTextContent('orders,customers,order-summary');
expect(screen.getByLabelText('Rendered relationships')).toHaveTextContent('orders-customers,summary-orders');
```

Also test that selecting an entity and changing mode removes the selected-detail inspector, that the canvas local state returns to `false` after a mode change, and that a schema with only views initially shows “No tables in this schema.” but renders after selecting Views.

- [ ] **Step 2: Run application tests and confirm failure**

```powershell
rtk npm run test:run -- src/App.test.tsx
```

Expected: FAIL because `App` always passes the complete graph and does not supply selector props.

- [ ] **Step 3: Implement application ownership and graph derivation**

In `App.tsx`, add:

```ts
const [displayMode, setDisplayMode] = useState<EntityDisplayMode>('tables');
const renderedGraph = useMemo(
  () => graph ? filterGraph(graph, displayMode) : null,
  [graph, displayMode],
);
const inspectedTable = renderedGraph?.tables.find((table) => table.id === selectedTable?.id) ?? null;
```

Add a mode-change handler that clears selection before updating mode:

```ts
function changeDisplayMode(mode: EntityDisplayMode) {
  setSelectedTable(null);
  setDisplayState(null);
  setDisplayMode(mode);
}
```

Render heading relationship counts and empty states from `renderedGraph`. Pass `renderedGraph` to `ErdCanvas`, and key it by both schema and mode:

```tsx
<ErdCanvas
  key={`${loadedSchemaId ?? graph.schema.id}:${displayMode}`}
  graph={renderedGraph}
  onSelectedTableChange={setSelectedTable}
  onDisplayStateChange={setDisplayState}
/>
```

Pass the complete `graph`, `displayMode`, and `onDisplayModeChange={changeDisplayMode}` to `InspectorPanel`; its full graph is required for stable table/view totals while the canvas actions still come from the filtered canvas.

Reset `displayMode` to `'tables'` only when the catalog selection is completely cleared or the app remounts; preserve the user choice when changing schemas during the same session.

- [ ] **Step 4: Generalize canvas display-state terminology**

Rename only public-facing copy, not stable internal fields in this task:

- “Collapse all tables” → “Collapse all entities”
- “Expand all tables” → “Expand all entities”
- “Restore all hidden tables” → “Restore all hidden entities”
- `CanvasDisplayState.hiddenTableIds` → `hiddenEntityIds`

Update `ErdCanvas`, `InspectorPanel`, `App`, and their tests together so TypeScript catches every consumer. Keep `graph.tables`, `TableModel`, `TableNode`, and relationship endpoint fields unchanged per the global constraint.

- [ ] **Step 5: Run focused frontend tests**

```powershell
rtk npm run test:run -- src/App.test.tsx src/components/InspectorPanel.test.tsx src/components/ErdCanvas.test.tsx src/graph/entityFilter.test.ts
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit application integration**

```powershell
rtk git add frontend/src/App.tsx frontend/src/App.test.tsx frontend/src/components/ErdCanvas.tsx frontend/src/components/ErdCanvas.test.tsx frontend/src/components/InspectorPanel.tsx frontend/src/components/InspectorPanel.test.tsx
rtk git commit -m "feat: render ERD tables views or both"
```

---

### Task 5: Label views and update fallback/sample fixtures

**Files:**
- Modify: `frontend/src/components/TableNode.tsx`
- Modify: `frontend/src/components/ErdCanvas.test.tsx`
- Modify: `frontend/src/styles.css`
- Modify: `backend/app/sample_graph.json`
- Test: `backend/tests/test_api.py`

**Interfaces:**
- Consumes: `TableModel.entityType`.
- Produces: visible `VIEW` badge and accessible node label `<name> view` for views; all sample entities satisfy the backend contract.

- [ ] **Step 1: Write a failing view-node test**

Add a view to the `ErdCanvas.test.tsx` graph and assert:

```ts
expect(await screen.findByRole('article', { name: 'Order summary view, expanded' })).toBeInTheDocument();
expect(screen.getByText('VIEW')).toBeInTheDocument();
```

- [ ] **Step 2: Run the canvas test and confirm failure**

```powershell
rtk npm run test:run -- src/components/ErdCanvas.test.tsx
```

Expected: FAIL because every node currently uses “table” labeling and no view badge exists.

- [ ] **Step 3: Render entity-aware node labels**

In `TableNode.tsx`, derive:

```ts
const entityLabel = table.entityType === 'view' ? 'view' : 'table';
```

Use it in the article and selection accessible names, and render beside the entity name:

```tsx
{table.entityType === 'view' && <span className="entity-type-badge">VIEW</span>}
```

Style it compactly:

```css
.entity-type-badge { padding: 2px 5px; border: 1px solid var(--accent); border-radius: 999px; color: var(--accent); font-size: 9px; line-height: 1; letter-spacing: .06em; }
```

- [ ] **Step 4: Update the bundled sample contract**

Add `"entityType": "table"` to current sample entities. Add one small `"entityType": "view"` entity named `Order Summary` with at least one column and a stable ID. Add or reuse one valid relationship involving it so Both mode visibly differs from Tables mode. Do not change the sample’s `source`, schema identity, or warning text.

Add an API assertion that every returned sample entity has `entityType` in `{"table", "view"}` and at least one sample entity is a view.

- [ ] **Step 5: Run sample and canvas tests**

Run from the repository root:

```powershell
rtk pytest backend/tests/test_api.py -q
rtk npm run test:run --prefix frontend -- src/components/ErdCanvas.test.tsx
```

Expected: both commands pass.

- [ ] **Step 6: Commit entity labeling and sample data**

```powershell
rtk git add frontend/src/components/TableNode.tsx frontend/src/components/ErdCanvas.test.tsx frontend/src/styles.css backend/app/sample_graph.json backend/tests/test_api.py
rtk git commit -m "feat: label views in ERD nodes"
```

---

### Task 6: Cover the complete browser flow and document the behavior

**Files:**
- Modify: `frontend/e2e/erd-viewer.spec.ts`
- Modify: `docs/superpowers/specs/2026-10-21-openmetadata-erd-viewer-design.md`

**Interfaces:**
- Consumes: final API contract and accessible selector/node labels.
- Produces: regression coverage for the user-visible workflow and an updated source-of-truth design.

- [ ] **Step 1: Extend the E2E fixture and assertions**

Add `entityType: 'table'` to Customer and Orders, then add an `Order Summary` entity with `entityType: 'view'`. Add a relationship from the view to Orders.

Before existing canvas interactions, assert the default and transitions:

```ts
await expect(page.getByRole('radio', { name: 'Tables' })).toBeChecked();
await expect(page.getByRole('group', { name: 'Order Summary view', exact: true })).toHaveCount(0);

await page.getByRole('radio', { name: 'Views' }).check();
await expect(page.getByRole('group', { name: 'Customer table', exact: true })).toHaveCount(0);
await expect(page.getByRole('group', { name: 'Order Summary view', exact: true })).toBeVisible();

await page.getByRole('radio', { name: 'Both' }).check();
await expect(page.getByRole('group', { name: 'Customer table', exact: true })).toBeVisible();
await expect(page.getByRole('group', { name: 'Order Summary view', exact: true })).toBeVisible();
```

Return to Tables before continuing the existing table interaction steps so that test remains deterministic.

- [ ] **Step 2: Update the design document**

Document these exact decisions:

- `TableModel` includes normalized `entityType: "table" | "view"`.
- Tables is the default display mode.
- View, SecureView, and MaterializedView normalize to view; other types normalize to table.
- Filtering occurs in the browser and removes relationships whose endpoint is filtered.
- Mode is retained across schema selections within the session, but not persisted across reloads.
- Mode changes reset ephemeral canvas state and selection.

Update success criteria, graph-contract example, `InspectorPanel`, interaction model, empty states, and testing strategy.

- [ ] **Step 3: Run the E2E test**

Run from `frontend` with the configured test server prerequisites:

```powershell
rtk npm run test:e2e -- erd-viewer.spec.ts
```

Expected: the ERD viewer test passes with no browser page errors.

- [ ] **Step 4: Run full verification**

Run from the repository root:

```powershell
rtk pytest backend/tests -q
rtk npm run test:run --prefix frontend
rtk npm run build --prefix frontend
rtk npm run test:e2e --prefix frontend -- erd-viewer.spec.ts
```

Expected: all backend tests, frontend unit tests, TypeScript/Vite build, and the ERD E2E test pass.

- [ ] **Step 5: Review the final diff for scope and contract consistency**

```powershell
rtk git diff --check
rtk git diff --stat
rtk git status --short
```

Expected: no whitespace errors; only the files listed by this plan are changed, apart from pre-existing untracked user files.

- [ ] **Step 6: Commit documentation and E2E coverage**

```powershell
rtk git add frontend/e2e/erd-viewer.spec.ts docs/superpowers/specs/2026-10-21-openmetadata-erd-viewer-design.md
rtk git commit -m "test: cover ERD table and view modes"
```

---

## Acceptance criteria

- A fresh application renders only entities classified as tables.
- The inspector offers accessible Tables, Views, and Both choices.
- Views mode renders only views; Both renders all entities.
- Relationships with a filtered endpoint are not rendered.
- Switching mode clears selection and presents a newly laid-out, fitted canvas.
- Explicitly hidden entities are never counted as category-filtered entities.
- View cards are visibly and accessibly distinguishable from tables.
- Mode-specific counts and empty states are accurate.
- The fallback sample supports all three modes.
- Backend unit/API tests, frontend unit tests, frontend build, and E2E test pass.
