# Cross-Schema Notices and Theme Choice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace noisy cross-schema FK warnings with one neutral count and add a remembered System/Light/Dark theme choice.

**Architecture:** The backend classifies FK targets using parsed FQNs and adds `notices` to `GraphResponse`; real same-schema metadata faults remain warnings. A focused frontend theme module owns preference persistence and system-theme resolution, while semantic CSS variables supply complete dark and light palettes.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, OpenMetadata SDK, React 19, TypeScript, Vitest/Testing Library, React Flow, CSS custom properties.

## Global Constraints

- Do not load external tables or render cross-schema edges.
- Do not add OpenMetadata calls.
- Aggregate omitted FK column relationships with exact singular/plural grammar.
- Default theme preference is `system`; remember `system`, `light`, or `dark` in `localStorage`.
- Preserve all read-only, fallback, filtering, layout, and interaction behavior.
- Follow repository instructions by prefixing shell commands with `rtk`.

---

### Task 1: Classify Cross-Schema Relationships

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/catalog_service.py`
- Modify: `backend/app/sample_graph.json`
- Test: `backend/tests/test_catalog_service.py`
- Test: `backend/tests/test_api.py`

**Interfaces:**
- Produces: `GraphResponse.notices: list[str]`.
- Produces: `_map_relationships(tables, selected_schema_fqn, warnings) -> tuple[list[RelationshipModel], int]`.
- Consumes: OpenMetadata FQNs parsed with `metadata.utils.fqn.split`.

- [ ] **Step 1: Add failing backend tests**

Add focused tests proving a valid external reference returns no edge or warning and count `1`, multiple external columns aggregate, and a malformed same-schema reference remains a warning. Extend API/sample assertions with `notices`.

```python
relationships, omitted = _map_relationships([orders], "svc.db.sales", warnings)
assert relationships == []
assert omitted == 1
assert warnings == []
```

- [ ] **Step 2: Run the focused tests and verify failure**

Run: `rtk proxy .venv\Scripts\python.exe -m pytest backend/tests/test_catalog_service.py backend/tests/test_api.py -q`

Expected: FAIL because `GraphResponse` and `_map_relationships` do not expose notices/classification.

- [ ] **Step 3: Implement classification and graph notices**

Add `notices` with a default factory. Parse the selected schema FQN and each referred column FQN; references whose table's parent components differ from the selected schema increment the omitted count before table lookup. Assemble exactly:

```python
notice = (
    f"{count} cross-schema relationship is not shown."
    if count == 1
    else f"{count} cross-schema relationships are not shown."
)
```

Invalid FQNs and missing same-schema entities remain warnings. Add `"notices": []` to the sample fixture.

- [ ] **Step 4: Run backend tests**

Run: `rtk proxy .venv\Scripts\python.exe -m pytest backend/tests -q`

Expected: all backend tests pass.

- [ ] **Step 5: Commit the backend slice**

```powershell
rtk git add backend/app/models.py backend/app/catalog_service.py backend/app/sample_graph.json backend/tests/test_catalog_service.py backend/tests/test_api.py
rtk git commit -m "feat: summarize omitted cross-schema relationships"
```

### Task 2: Render Neutral Notices

**Files:**
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/StatusBanner.tsx`
- Modify: `frontend/src/styles.css`
- Test: `frontend/src/App.test.tsx`
- Test: `frontend/src/components/StatusBanner.test.tsx` (create if absent)
- Modify: `frontend/e2e/erd-viewer.spec.ts`

**Interfaces:**
- Consumes: `GraphResponse.notices: string[]`.
- Produces: `StatusBannerProps.notices: string[]` and accessible `Diagram notices` region.

- [ ] **Step 1: Add failing frontend tests**

Test that notices render separately from warnings and that an empty notice list keeps the banner hidden when no other status exists.

```tsx
render(<StatusBanner loading={false} error={null} source="live"
  notices={["2 cross-schema relationships are not shown."]} warnings={[]} />);
expect(screen.getByRole('status', { name: 'Diagram notices' })).toHaveTextContent('2 cross-schema');
```

- [ ] **Step 2: Run focused tests and verify failure**

Run: `rtk proxy npm.cmd run test:run --prefix frontend -- App.test.tsx StatusBanner`

Expected: FAIL because notice props and rendering do not exist.

- [ ] **Step 3: Implement notice typing and presentation**

Add `notices` to the type and pass `graph?.notices ?? []` from `App`. Render neutral notice content with `.notice-status`, preserving independent warning/sample/error states. Update all fixtures to include `notices: []`.

- [ ] **Step 4: Run frontend unit tests**

Run: `rtk proxy npm.cmd run test:run --prefix frontend`

Expected: all frontend tests pass.

- [ ] **Step 5: Commit notice UI**

```powershell
rtk git add frontend/src frontend/e2e/erd-viewer.spec.ts
rtk git commit -m "feat: display cross-schema relationship notices"
```

### Task 3: Add Remembered Theme Preference

**Files:**
- Create: `frontend/src/theme.ts`
- Create: `frontend/src/theme.test.ts`
- Create: `frontend/src/components/ThemeControl.tsx`
- Create: `frontend/src/components/ThemeControl.test.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/index.html`
- Modify: `frontend/src/test/setup.ts`

**Interfaces:**
- Produces: `ThemePreference = 'system' | 'light' | 'dark'`.
- Produces: `readThemePreference(storage)`, `resolveTheme(preference, mediaQuery)`, and `applyTheme(theme)`.
- Produces: `<ThemeControl />`, which stores preference under `omd-erd-theme`.

- [ ] **Step 1: Add failing theme-state tests**

Cover missing/invalid storage, saved values, light/dark resolution, system media changes, and storage exceptions.

```ts
expect(readThemePreference(storageWith('light'))).toBe('light');
expect(readThemePreference(storageWith('invalid'))).toBe('system');
expect(resolveTheme('system', { matches: true })).toBe('dark');
```

- [ ] **Step 2: Add failing control tests**

Render the control, select Light, verify `document.documentElement.dataset.theme === 'light'`, verify storage, and then choose System and fire a media-query change.

- [ ] **Step 3: Run focused tests and verify failure**

Run: `rtk proxy npm.cmd run test:run --prefix frontend -- theme ThemeControl`

Expected: FAIL because the theme module and control do not exist.

- [ ] **Step 4: Implement theme state and control**

Use guarded storage access and `matchMedia('(prefers-color-scheme: dark)')`. Set `data-theme` and `colorScheme` on the root. Use an accessible labelled select with System, Light, and Dark options. Subscribe to media changes only while System is selected.

- [ ] **Step 5: Define complete semantic light palette**

Retain current variables under `:root, :root[data-theme='dark']`; define light equivalents under `:root[data-theme='light']`. Replace remaining hard-coded dark-only colors with semantic variables, including column separators, related borders, tags, and status background/border colors.

- [ ] **Step 6: Prevent startup theme flash**

Add a short guarded inline script in `frontend/index.html` that validates `omd-erd-theme`, resolves System through `matchMedia`, and sets `data-theme` before the stylesheet paints.

- [ ] **Step 7: Run frontend tests, typecheck, and build**

Run:

```powershell
rtk proxy npm.cmd run test:run --prefix frontend
rtk proxy npm.cmd exec --prefix frontend tsc -- --noEmit --project frontend/tsconfig.json
rtk proxy npm.cmd run build --prefix frontend
```

Expected: all tests pass, TypeScript emits no errors, and Vite builds successfully.

- [ ] **Step 8: Commit theming**

```powershell
rtk git add frontend/index.html frontend/src
rtk git commit -m "feat: add remembered light and dark themes"
```

### Task 4: Documentation and End-to-End Verification

**Files:**
- Modify: `README.md`
- Modify: `frontend/e2e/erd-viewer.spec.ts`

**Interfaces:**
- Consumes: final API notices and theme control.
- Produces: documented and browser-verified user workflow.

- [ ] **Step 1: Extend the browser scenario**

Assert the aggregate notice, select Light, reload and confirm Light remains selected, select System, and retain existing ERD interaction assertions.

- [ ] **Step 2: Update user documentation**

Document that cross-schema relationships are counted but not rendered, malformed same-schema metadata remains a warning, and System/Light/Dark preference is remembered locally.

- [ ] **Step 3: Run full verification**

Run:

```powershell
rtk proxy .venv\Scripts\python.exe -m pytest backend/tests -q
rtk proxy npm.cmd run test:run --prefix frontend
rtk proxy npm.cmd exec --prefix frontend tsc -- --noEmit --project frontend/tsconfig.json
rtk proxy npm.cmd run build --prefix frontend
rtk proxy npm.cmd run test:e2e --prefix frontend
```

Expected: every command succeeds.

- [ ] **Step 4: Confirm live Sales behavior**

Request the running Sales graph with refresh and verify 22 same-schema relationships, one notice stating 12 omitted cross-schema relationships, and no cross-schema unresolved warnings.

- [ ] **Step 5: Commit documentation and E2E coverage**

```powershell
rtk git add README.md frontend/e2e/erd-viewer.spec.ts
rtk git commit -m "docs: explain relationship notices and themes"
```
