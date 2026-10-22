# Cross-Schema Notices and Theme Choice Design

## Purpose

Improve the ERD viewer without expanding its graph boundary. Cross-schema relationships remain intentionally omitted, but the application stops presenting each omission as an unresolved-foreign-key warning. Users also gain an accessible light theme alongside the existing dark theme, with their explicit choice remembered in the browser.

Loading cross-linked external tables and views is explicitly parked for separate future design work.

## Goals

- Preserve the selected-schema graph boundary.
- Distinguish intentionally omitted cross-schema relationships from malformed same-schema relationships.
- Replace repetitive cross-schema warnings with one neutral counted notice.
- Retain detailed warnings for genuine relationship-data problems.
- Offer system, light, and dark theme choices.
- Remember an explicit light or dark choice across visits.
- Apply the selected theme to the entire shell and ERD, including React Flow elements.

## Non-goals

- Loading or rendering tables and views outside the selected schema.
- Rendering cross-schema edges.
- Recursive relationship traversal.
- Persisting theme preferences on the server or sharing them between browsers.
- Introducing a component framework or third-party theme library.
- Redesigning the existing layout or visual identity.

## Relationship classification

The graph mapper classifies every declared foreign-key column relationship into one of three outcomes.

### Valid same-schema relationship

The referenced table exists in the selected schema, the source and target columns exist, and the reference shape is valid. The mapper emits the relationship normally.

### Cross-schema relationship

The reference is structurally valid but its target table belongs to another schema. The mapper omits the edge and increments a cross-schema omission count. It does not emit an unresolved-foreign-key warning.

Schema membership is determined from parsed FQN components. The implementation must not infer it from display names or unparsed string prefixes.

### Malformed or unresolved same-schema relationship

The reference claims a target in the selected schema but has mismatched local and referred column counts, an invalid FQN, a missing table, or a missing source or target column. The mapper retains a detailed warning because this indicates malformed or incomplete metadata rather than an intentional scope boundary.

## Graph contract

`GraphResponse` gains a neutral informational field:

```json
{
  "source": "live",
  "schema": {
    "id": "schema-id",
    "name": "Sales",
    "fullyQualifiedName": "MSSQL Desktop.AdventureWorks2019.Sales"
  },
  "tables": [],
  "relationships": [],
  "notices": [
    "12 cross-schema relationships are not shown."
  ],
  "warnings": []
}
```

The omission count represents foreign-key column relationships, matching the current one-edge-per-column mapping behavior. Grammar is singular for one relationship and plural otherwise. A graph with no cross-schema references returns an empty `notices` list.

The bundled sample graph includes `notices: []` unless it intentionally contains an omitted cross-schema relationship. Existing graph consumers treat a missing field only as a temporary compatibility case during rollout; the final backend contract always serializes the field.

## Backend structure

Relationship mapping receives enough selected-schema context to classify target references before attempting target-table lookup. The mapper returns both resolved relationships and classification results, rather than communicating all non-rendered relationships through one warning list.

Responsibilities remain separated:

- FQN parsing determines whether a structurally valid target belongs to the selected schema.
- Relationship validation confirms source table, target table, source column, and target column existence.
- Graph assembly converts the cross-schema count into one notice and carries genuine warnings unchanged.

No additional OpenMetadata requests are made. Cache behavior is unchanged because notices are part of the cached graph response.

## Frontend status presentation

The frontend `GraphResponse` type gains `notices: string[]`. `StatusBanner` renders notices as neutral information, visually distinct from warnings, request errors, loading state, and the sample-data banner.

For the current AdventureWorks Sales schema, the user sees one message:

> 12 cross-schema relationships are not shown.

The status region remains accessible. Multiple notices, if introduced later, render independently with stable keys. Notices do not prevent interaction and do not imply that the loaded graph is incomplete within its supported selected-schema boundary.

## Theme model

The browser supports three theme preferences:

- `system`: follow the operating-system color-scheme preference;
- `light`: always use the light palette;
- `dark`: always use the dark palette.

The first visit defaults to `system`. Once the user explicitly chooses light or dark, the preference is stored in `localStorage` and restored on later visits. Choosing system stores `system`, making the user's return to automatic behavior explicit.

The storage key is application-specific and version-stable. Only the three valid values are accepted. Missing, malformed, or inaccessible storage falls back to system mode without preventing application startup.

While preference is system, changes to `prefers-color-scheme` update the effective theme immediately. OS changes do not override an explicit light or dark choice.

## Theme application

A focused theme-state module owns:

- reading and validating the stored preference;
- resolving system preference to the effective light or dark theme;
- subscribing to system-theme changes only when needed;
- applying the effective theme to the document root;
- persisting explicit user changes.

The application header contains a compact, keyboard-accessible control exposing System, Light, and Dark. It communicates the current selected preference, not merely the currently resolved palette.

The document root receives a stable theme attribute before or during React startup. Startup should avoid displaying the dark palette before restoring a saved light preference. The implementation may use a small non-secret inline initialization script in `index.html` if React initialization alone produces a visible flash.

## Visual palette

The current dark palette remains the dark-theme definition. Existing CSS custom properties become the semantic source for both themes.

The light theme defines equivalents for:

- page, header, canvas, inspector, and elevated-card surfaces;
- primary, muted, and disabled text;
- borders, shadows, focus rings, and active controls;
- violet accent and selection states;
- neutral notices, warnings, errors, and sample status;
- canvas dots, table nodes, relationship edges, edge labels, and arrowheads;
- React Flow controls and attribution where visible.

Light colors must maintain readable contrast and preserve the visual distinction among table cards, the canvas, selected entities, dimmed entities, notices, and warnings. Theme selection does not change spacing, typography, layout, animation behavior, or entity colors used to communicate state.

## Error handling

- Storage access errors are caught and ignored; the application uses system mode.
- Invalid stored values are ignored and replaced only when the user makes a valid selection.
- A missing or older `notices` field is normalized to an empty list at the API boundary during rollout.
- Invalid relationship FQNs remain warnings because their schema membership cannot be established safely.
- Valid references outside the selected schema never become warnings merely because their target was intentionally not loaded.
- Empty schemas and schemas without cross-schema references do not display a notice.

## Testing strategy

### Backend unit tests

- A valid same-schema foreign key still produces an edge and no notice.
- One valid cross-schema foreign key produces no edge, one counted notice, and no warning.
- Multiple cross-schema foreign-key columns produce one pluralized aggregate notice.
- A mixture of cross-schema and malformed same-schema references produces both the neutral notice and the genuine warning.
- Invalid FQNs remain warnings.
- Quoted FQN components classify correctly.
- Cache hits retain notices and refresh recomputes them.

### API tests

- Live, empty, and sample graph responses serialize `notices`.
- The Sales-shaped fixture returns the aggregated notice instead of individual unresolved warnings.
- Existing response aliases and read-only route behavior remain unchanged.

### Frontend tests

- Notices render as neutral accessible status content.
- Warnings, notices, errors, loading, and sample status can coexist without being conflated.
- A missing transitional `notices` field is treated as empty.
- First visit uses system preference.
- Saved light and dark preferences restore correctly.
- Selecting each preference updates the document theme and storage.
- Returning to system resumes reaction to OS theme changes.
- Invalid values and storage exceptions fall back safely.
- The theme control exposes an accessible name, selected state, and keyboard interaction.

### Visual and end-to-end verification

- Exercise schema selection and core ERD interactions in both light and dark themes.
- Verify the shell, canvas, nodes, edges, controls, inspector, notices, warnings, focus states, and empty states in both themes.
- Reload after selecting light and dark and confirm preference restoration.
- Load AdventureWorks Sales and confirm one cross-schema notice, no repetitive cross-schema warnings, and all same-schema edges still render.
- Run backend tests, frontend tests, TypeScript checking, production build, and the browser suite.

## Documentation changes

Update the README to state that:

- only relationships whose endpoints are in the selected schema are rendered;
- omitted cross-schema relationships are summarized as neutral information;
- genuine malformed relationship metadata still produces warnings;
- users can select System, Light, or Dark and the browser remembers that preference.

Remove cross-schema edges from the broad exclusions wording only if that wording becomes ambiguous; cross-schema rendering itself remains excluded.

## Acceptance criteria

- AdventureWorks Sales shows one counted cross-schema notice rather than twelve unresolved warnings.
- Valid same-schema relationships remain unchanged.
- Malformed same-schema relationship metadata still produces actionable warnings.
- No additional OpenMetadata calls occur.
- System, light, and dark are selectable from the header.
- Explicit theme selection survives reload in the same browser.
- System mode follows OS preference changes.
- Every major application and ERD surface is legible and functionally equivalent in light and dark themes.
- Existing read-only, fallback, filtering, layout, and interaction behavior continues to pass.
