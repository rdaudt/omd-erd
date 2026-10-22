# OpenMetadata ERD Viewer Design

## Purpose

Build a local demonstration application that showcases OpenMetadata 2.0.5 as an extensible metadata platform whose catalog capabilities are available through APIs. The application presents a read-only entity-relationship diagram for one relational database schema at a time.

The demo is aimed at a data architecture audience. Its visual centerpiece is a polished ERD canvas, while its inspector exposes broader OpenMetadata context such as descriptions, ownership, tags, and tiers.

## Success criteria

- Users select an OpenMetadata database service, database, and schema in that order.
- A schema containing up to 50 tables renders as a readable ERD.
- Users can render tables only, views only, or both; tables only is the default.
- Only declared foreign-key relationships appear as edges.
- Users can drag tables, pan and zoom the canvas, fit the diagram to view, and rerun automatic layout.
- Users can collapse or expand individual tables and all visible tables.
- Users can hide and restore tables; hiding a table also hides its connected edges.
- Selecting a table highlights its immediate relationships and displays rich OpenMetadata metadata.
- Diagram changes remain in browser memory and are discarded on schema change or refresh.
- The application never modifies OpenMetadata.
- If live OpenMetadata becomes unavailable, a clearly labeled sample diagram keeps the demonstration usable.

## Scope

### Included

- Local React application with a modern midnight canvas
- Local FastAPI adapter backed by `openmetadata-ingestion==2.0.5.1`
- Service, database, and schema discovery
- Table, column, constraint, description, owner, tag, and tier retrieval
- Primary-key and foreign-key presentation
- Initial automatic layout with ELK.js
- Interactive rendering with React Flow
- Live-data and fallback-sample states
- Automated backend, frontend, transformation, and end-to-end tests

### Excluded

- Metadata or relationship editing
- Saved or shareable diagram layouts
- Image, PDF, or model export
- Authentication screens and application-level authorization
- Lineage edges or inferred relationships
- Cross-schema relationships
- Collaboration and multi-user state
- Production deployment
- Mobile-specific design
- Rendering guarantees for schemas larger than 50 tables

## Architecture

The application has three isolated units.

### React frontend

The browser application owns presentation and ephemeral interaction state. It renders the graph, performs the initial ELK layout, and records table positions, visibility, collapse state, selection, and viewport state in memory only. It does not receive the OpenMetadata JWT and does not call OpenMetadata directly.

### FastAPI adapter

The local Python service owns the OpenMetadata URL and JWT, loaded from environment variables. It uses the version-matched OpenMetadata Python SDK to read catalog entities, handles pagination, and maps generated OpenMetadata models into a small frontend-specific graph contract.

The adapter exposes only read operations. It provides no generic proxy endpoint and accepts no arbitrary OpenMetadata API paths from the browser.

### OpenMetadata 2.0.5

The local Docker deployment remains the sole source of live metadata. The application performs read-only API calls and never changes catalog state.

## Backend API

The FastAPI service exposes four GET endpoints:

- `GET /api/services`
- `GET /api/databases?serviceId={serviceId}`
- `GET /api/schemas?databaseId={databaseId}`
- `GET /api/schemas/{schemaId}/graph`

Child-list endpoints validate their parent IDs. The graph endpoint retrieves the schema's tables and required fields, follows pagination to completion, normalizes constraints and metadata, and returns one response suitable for direct graph construction.

Responses may be held in a short-lived in-process cache. A manual refresh request bypasses that cache. The cache is a responsiveness optimization, not persistent storage.

## Graph contract

The graph response has this conceptual form:

```json
{
  "source": "live",
  "schema": {
    "id": "schema-id",
    "name": "Person",
    "fullyQualifiedName": "MSSQL Desktop.AdventureWorks2019.Person"
  },
  "tables": [
    {
      "id": "table-id",
      "name": "Address",
      "fullyQualifiedName": "MSSQL Desktop.AdventureWorks2019.Person.Address",
      "entityType": "table",
      "description": "Postal addresses used by customers and vendors.",
      "owner": "Data Architecture",
      "tags": ["PII.Sensitive"],
      "tier": "Tier1",
      "columns": [
        {
          "name": "AddressID",
          "dataType": "INT",
          "nullable": false,
          "primaryKey": true,
          "foreignKey": false,
          "description": "Surrogate identifier."
        }
      ]
    }
  ],
  "relationships": [
    {
      "id": "stable-relationship-id",
      "sourceTableId": "source-table-id",
      "sourceColumn": "AddressID",
      "targetTableId": "target-table-id",
      "targetColumn": "AddressID"
    }
  ],
  "warnings": []
}
```

`source` is either `live` or `sample`. Relationship IDs are stable within a graph response and derived from their endpoints when OpenMetadata does not supply a suitable constraint identifier.

`entityType` is normalized to `table` or `view`. OpenMetadata `View`, `SecureView`, and `MaterializedView` values map to `view`; all other, missing, and future values map to `table` so existing entities remain visible by default.

## Frontend structure

### `CatalogSelector`

Renders cascading service, database, and schema selectors. Changing a parent clears all child selections and any displayed graph. Rapid changes cancel or invalidate stale requests.

### `ErdCanvas`

Owns React Flow nodes, edges, viewport behavior, selection, and ephemeral diagram state. It invokes ELK after a graph loads or when the user requests relayout. It fits the completed layout into view.

### `TableNode`

Renders a custom table card. Expanded cards show all columns with type, nullability, and key indicators. Collapsed cards show the table name and compact counts. The node is selectable and draggable but never connectable or editable.

### `RelationshipEdge`

Renders a directed foreign-key connection with source and target column labels. Edges are read-only and visually emphasized when either endpoint is selected.

### `InspectorPanel`

The panel always presents a Tables, Views, or Both display selector. When no entity is selected, it also presents diagram counts, display settings, and hidden-entity restoration. When an entity is selected, it shows description, owner, tags, tier, columns, primary keys, and incoming and outgoing foreign keys.

### `CanvasControls`

Provides zoom in, zoom out, fit-to-view, automatic relayout, collapse all, expand all, and restore-all-hidden actions.

### `StatusBanner`

Communicates loading, non-blocking warnings, and data source. Fallback mode always displays a persistent `Sample data — OpenMetadata unavailable` label.

## Interaction model

- Selecting a schema requests its complete graph once.
- The browser filters the complete graph by the selected display mode; relationships render only when both endpoints remain.
- Tables is the initial mode. The mode is retained while changing schemas in the current session, but is not persisted across a browser reload.
- Changing display mode clears selection and resets ephemeral canvas layout, hide, collapse, pan, and zoom state.
- ELK produces the initial positions; users may then reposition tables freely.
- Dragging, hiding, expanding, collapsing, zooming, and panning affect browser memory only.
- Hiding a table hides all incident edges without deleting graph data.
- Hidden tables are listed in the inspector and can be restored individually or together.
- Selecting a table highlights that table, directly related tables, and incident edges. Unrelated elements are visually dimmed.
- Changing schema or refreshing the browser resets all ephemeral state.
- A manual relayout discards current table positions but retains the current visibility and collapse choices.

## Visual design

The selected direction is a full-height midnight canvas with a right-side inspector.

- Deep neutral backgrounds minimize glare and improve projector contrast.
- Table cards use elevated charcoal surfaces with crisp typography.
- Violet accents identify selected nodes, relationships, controls, and active states.
- A subtle dot grid communicates a navigable modeling canvas.
- Motion is brief and functional: panel transitions, selection emphasis, node expansion, and fit/relayout viewport animation.
- The service, database, and schema path remains visible in the top bar.
- The inspector remains present so controls and selected metadata have a stable location.

## Loading, empty, and failure states

- Selector requests show localized loading states and preserve the last successful canvas where appropriate.
- Graph loading shows a canvas skeleton and prevents conflicting diagram actions.
- An empty display mode shows a mode-specific message for no tables, no views, or no tables or views, and is not replaced by sample data.
- Missing optional metadata renders as absent or `Not assigned`, not as an error.
- Malformed or unresolved foreign keys are skipped, counted, and reported as a non-blocking warning.
- OpenMetadata calls use bounded timeouts.
- When the initial live graph request fails because OpenMetadata is unavailable, the backend returns the bundled sample graph with `source: sample` and an explanatory warning.
- The frontend never silently presents sample data as live metadata.
- Technical errors are logged by the backend without logging the JWT. User-facing messages remain concise and actionable.

## Security boundary

No user authentication or authorization UI is required for this laptop demo. The OpenMetadata JWT remains in the FastAPI process environment and is never embedded in the frontend bundle or API responses. The adapter listens locally, exposes only fixed read-only routes, and does not implement OpenMetadata write calls.

## Testing strategy

### Backend unit tests

Mock the OpenMetadata SDK and verify hierarchy mapping, pagination, field normalization, PK/FK extraction, relationship direction, missing optional metadata, malformed constraints, timeout handling, and fallback activation.

### Backend API tests

Verify the four GET endpoints, parent-child validation, response models, live and sample labels, cache bypass, error status behavior, and the absence of write routes.

### Frontend tests

Verify selector cascading, graph loading states, table/view/both filtering with tables as the default, entity expansion and collapse, hide and restore behavior, connected-edge visibility, inspector content, relationship highlighting, and source banners.

### Graph transformation tests

Verify that backend graph data maps deterministically to React Flow nodes and edges, ELK positions are applied correctly, hidden nodes remove incident edges from the rendered set, and schema changes reset ephemeral state.

### End-to-end test

Exercise the representative flow: select a service, database, and schema; render the ERD; drag and collapse a table; hide and restore it; zoom and fit the graph; select a table; and inspect its metadata.

### Manual demo check

Before presenting, start the actual local OpenMetadata 2.0.5 stack, select a visually useful schema with declared foreign keys, confirm live-data labeling, exercise every canvas control, and briefly test the fallback path.

## Local operation

The project provides separate development commands for the FastAPI backend and React frontend plus one documented convenience command to start both. The backend uses the existing project virtual environment running Python 3.12.10. The frontend uses a current supported Node.js toolchain. Configuration is loaded from local environment variables, and secrets are excluded from version control.

## Implementation direction

- React with TypeScript
- React Flow for the interactive graph canvas
- ELK.js for initial and user-requested automatic layout
- FastAPI with Pydantic response models
- OpenMetadata Python SDK `2.0.5.1`
- A lightweight frontend test runner and Testing Library
- Pytest for backend tests
- A browser-level test runner for the single end-to-end demo flow

