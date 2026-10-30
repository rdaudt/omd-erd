# Data Marketplace Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone Data Marketplace demo app (search, data product detail, request access) on top of the local OpenMetadata API, with a ServiceNow look-alike screen opened in a new tab, plus a re-runnable seed that makes OMD metadata rich.

**Architecture:** A new top-level `marketplace/` folder holds a FastAPI service (OMD proxy, metadata shaping, in-memory access requests) that also serves a no-build static frontend (Bootstrap 5.3 + vanilla ES modules, WorkSafeBC look rebuilt from documented tokens). A separate `marketplace/seed/` package idempotently creates users, teams, domains, tags, a custom property, data products, quality tests and lineage in OMD through its REST API. Nothing in `backend/`, `frontend/`, `tools/` or the `erd_*.html` files is touched.

**Tech Stack:** Python 3.12 (reuse the repo-root `.venv`), FastAPI, httpx, pydantic-settings, pytest; Bootstrap 5.3.3 and Font Awesome 4.7 from cdnjs; Node `--test` for pure JS helpers.

**Spec:** `docs/superpowers/specs/2026-10-30-data-marketplace-demo-design.md`

## Global Constraints

- The existing ERD viewer (`backend/`, `frontend/`, `erd_*.html`) must not be changed or interfered with; the new app uses its own folder, run script and port **8100**.
- Catalog content comes live from the local OMD instance; nothing about data products is hard-coded in pages.
- The OMD token stays server-side. Config reads `OMD_HOST` and `OMD_TOKEN` from the repo-root `.env` or the process environment, read-only; no import of `backend/app` code.
- One start command, nothing to compile; frontend is plain HTML/CSS/JS (ES modules) on Bootstrap 5.3, no React, no build step.
- Persona is fixed: **John Analyst Doe**. No login, no persona switcher.
- Access is requested for a whole data product only; form fields are business justification and duration.
- The SNOW look-alike opens in a **new browser tab** and shows: data product title, user John Analyst Doe, the Entra group, justification and duration. It is static (no workflow steps).
- Natural-language search input is disabled, placeholder text only.
- Filters: domain, sensitivity, quality score, owner, certification. No admin screen, no cart, no My requests page.
- Datasets tab: table with dataset name and description. Views are excluded from datasets unless asked.
- WorkSafeBC tokens: orange `#ED8B00`, body `#453F39`, warm grey `#776E64`, Ash `#F1F0EF`, Silver `#E4E2E0`, Steel `#C9C5C1`, Smoke `#ADA8A2`, Iron `#47423C`, mountain blue `#6399AE`, huckleberry red `#A4343A`, sunset orange `#DC4405`, sunrise yellow `#F1BE48`, moss green `#888D30`; Noto body font with Verdana fallback; Font Awesome 4.7; fixed layout max width 1140px.
- Seed is additive and idempotent; it never overwrites existing descriptions, tags or glossary terms on tables.
- Shell commands are prefixed with `rtk` (user's global instruction); git commits end with the attribution lines from the session.

## Review Focus

1. Data product with no tables or no test results: quality shows "n/a", not 0 or a crash (Task 3, Task 4).
2. Data product with no Entra group: card and detail render "Not mapped"; request button disabled with a reason (Task 4, Task 8).
3. OMD unreachable or token rejected: API returns 503 with a readable message; pages show a banner, not a blank screen (Task 2, Task 6).
4. Descriptions or names from OMD containing HTML or markdown: rendered as escaped text, never injected as markup (Task 5).
5. Empty search/filter result, unknown product name (404 page with link back), empty justification (rejected with inline error) (Tasks 4, 6, 7, 8).

---

### Task 1: Verify OMD 2.0.5 capabilities (gate)

**Files:**
- Create: `marketplace/scripts/probe_omd.py`

**Interfaces:**
- Produces: a pass/fail printout; later tasks assume all checks pass. If check 1 fails, stop and bring the fallback to the user.

- [ ] **Step 1: Write `probe_omd.py`**, which reads `OMD_HOST`/`OMD_TOKEN` from the repo `.env` and uses httpx against `{OMD_HOST}/api/v1` to check, printing PASS/FAIL for each: (1) `GET /metadata/types?category=entity&limit=50` shows a `dataProduct` type and a custom property can be added via `PUT /metadata/types/{id}` with a string property; (2) `GET /dataProducts?limit=1` works and a data product accepts `assets` (via `PUT /dataProducts` with `assets` entity refs) and `experts`; (3) certification tags exist: `GET /tags?parent=Certification`; (4) `GET /dataQuality/testCases?limit=1` works; (5) `GET /lineage/table/name/{fqn}` works for an existing table. The probe must create nothing it cannot delete; use a throwaway type property and remove it.
- [ ] **Step 2: Run it**: `rtk python marketplace/scripts/probe_omd.py`. Expected: five PASS lines. On any FAIL for check 1, stop and report to the user.
- [ ] **Step 3: Commit** `docs/probe`: `rtk git add marketplace/scripts/probe_omd.py && rtk git commit -m "chore: probe OMD capabilities for marketplace demo"`

### Task 2: Scaffold, config and OMD client

**Files:**
- Create: `marketplace/pyproject.toml`, `marketplace/app/__init__.py`, `marketplace/app/config.py`, `marketplace/app/omd.py`, `marketplace/app/main.py`, `marketplace/tests/conftest.py`, `marketplace/tests/test_omd.py`, `marketplace/README.md` (stub, finished in Task 9)

**Interfaces:**
- Produces:
  - `Settings` (pydantic-settings; `omd_host: str` alias `OMD_HOST`, `omd_token: str` alias `OMD_TOKEN`, `request_timeout_seconds: float = 10.0`, `cache_ttl_seconds: int = 30`; env file = repo-root `.env`), `get_settings() -> Settings` (lru_cached).
  - `class OmdError(Exception)` with `status: int`, `message: str`.
  - `class OmdClient(settings: Settings, transport: httpx.BaseTransport | None = None)` with `get(path: str, params: dict | None = None) -> dict`, `put(path, json) -> dict`, `post(path, json) -> dict`, `patch(path, ops: list[dict]) -> dict`, `list_all(path, params=None, page_size=100) -> list[dict]` (follows `paging.after`). `path` is relative to `/api/v1`. Any httpx connect/timeout error or 401/5xx raises `OmdError`.
  - `main.app: FastAPI` with `GET /api/health -> {"status": "ok", "omd": "up" | "down"}` and an `OmdError` handler returning HTTP 503 `{"detail": message}`.
  - `conftest.py` fixture `omd_client_factory(handler)` building an `OmdClient` over `httpx.MockTransport`.

- [ ] **Step 1: Write failing tests** in `test_omd.py`: `test_list_all_follows_paging_after` (two pages, asserts concatenated items and `after` param), `test_get_sends_bearer_token`, `test_unreachable_raises_omd_error`, `test_401_raises_omd_error_with_status_401`; in `test_main.py`: `test_health_reports_omd_down_without_crashing`, `test_omd_error_becomes_503_with_message`.
- [ ] **Step 2: Run** `rtk pytest marketplace/tests -v`. Expected: FAIL (modules missing).
- [ ] **Step 3: Implement** the interfaces above. `pyproject.toml` declares deps `fastapi`, `httpx`, `pydantic-settings`, `uvicorn[standard]` and test extra `pytest`; `pythonpath = ["."]`, `testpaths = ["tests"]`. Install into the repo `.venv` with `rtk pip install -e "marketplace[test]"`.
- [ ] **Step 4: Run** `rtk pytest marketplace/tests -v`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(marketplace): scaffold service and OMD client`.

### Task 3: Pure shaping logic (quality, sensitivity, filtering)

**Files:**
- Create: `marketplace/app/models.py`, `marketplace/app/shaping.py`, `marketplace/tests/test_shaping.py`

**Interfaces:**
- Produces (`models.py`): `Sensitivity = Literal["Public","Internal","Confidential"]`; `ProductSummary` (pydantic: `name: str`, `display_name: str`, `description: str`, `domain: str | None`, `owners: list[str]`, `steward: str | None`, `certification: str | None` (one of `Gold`,`Silver`,`Bronze`), `table_count: int`, `quality: int | None`, `sensitivity: Sensitivity`, `entra_group: str | None`, `glossary_terms: list[str]`, `tags: list[str]`); `DatasetRow(name, fqn, description: str, quality: int | None)`; `TestResultRow(table: str, test: str, status: str)`; `LineageGraph(nodes: list[str], edges: list[tuple[str, str]])`; `ProductDetail(ProductSummary + datasets: list[DatasetRow], tests: list[TestResultRow], lineage: LineageGraph)`.
- Produces (`shaping.py`):
  - `table_quality(statuses: list[str]) -> int | None`: percent of `"Success"` among latest results, rounded; `None` if the list is empty.
  - `product_quality(table_scores: list[int | None]) -> int | None`: rounded mean of non-None; `None` if none.
  - `quality_bucket(score: int | None) -> Literal["90+","70-89","<70","n/a"]`.
  - `derive_sensitivity(tag_fqns: list[str]) -> Sensitivity`: any fqn starting `PII.Sensitive` or `PersonalData.` gives `Confidential`; else `Sensitivity.Internal` gives `Internal`; else `Public`; highest wins.
  - `filter_products(products: list[ProductSummary], *, domain=None, sensitivity=None, quality=None, owner=None, certification=None, q=None) -> list[ProductSummary]`: AND across filters, exact match except `q`, which is a case-insensitive substring over name, display name, description, glossary terms and tags. Unknown values return an empty list.
  - `facets(products) -> dict[str, list[str]]` with keys `domain`, `sensitivity`, `quality`, `owner`, `certification`, each the sorted distinct values present.

- [ ] **Step 1: Write failing tests** covering: `table_quality(["Success","Failed","Success","Success"]) == 75`; `table_quality([]) is None`; `product_quality([100, None, 80]) == 90`; `product_quality([None]) is None`; buckets at 90, 89, 70, 69 and None; `derive_sensitivity(["PII.Sensitive","Sensitivity.Internal"]) == "Confidential"`, `(["Sensitivity.Internal"]) == "Internal"`, `([]) == "Public"`; filter combos, `q` hitting a glossary term, an unknown domain returning `[]`; `facets` on an empty list returns empty lists.
- [ ] **Step 2: Run** `rtk pytest marketplace/tests/test_shaping.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `models.py` and `shaping.py` per the signatures.
- [ ] **Step 4: Run** same command. Expected: PASS.
- [ ] **Step 5: Commit** `feat(marketplace): metadata shaping and filtering`.

### Task 4: Catalog service and API endpoints

**Files:**
- Create: `marketplace/app/catalog.py`, `marketplace/app/requests_store.py`, `marketplace/tests/test_catalog.py`, `marketplace/tests/test_api.py`
- Modify: `marketplace/app/main.py`

**Interfaces:**
- Consumes: `OmdClient`, `shaping.*`, models from Task 3.
- Produces:
  - `catalog.CatalogService(client: OmdClient, ttl_seconds: int)` with `list_products() -> list[ProductSummary]` and `get_product(name: str) -> ProductDetail | None`, results cached for `ttl_seconds`. Reads `/dataProducts` with fields `domain,owners,experts,assets,tags,extension,certification` (hydrates a tag's glossary terms by `tags` whose `source == "Glossary"`), each asset table with `tags,columns,description` and `/dataQuality/testCases` results, and lineage via `/lineage/table/name/{fqn}`. Views (tableType `View`) are excluded. `entra_group` comes from `extension["entraGroup"]`. Certification maps from `certification.tagLabel.tagFQN` suffix.
  - `requests_store.AccessRequestStore` with `create(product: str, justification: str, duration: str, entra_group: str | None) -> AccessRequest` and `get(number: str) -> AccessRequest | None`; `AccessRequest(number: str, user: str, product_name: str, product_title: str, entra_group: str | None, justification: str, duration: str, opened_at: datetime)`; numbers are `REQ0010001`, incrementing; user is the constant `"John Analyst Doe"`.
  - Routes: `GET /api/products` accepting query params `domain, sensitivity, quality, owner, certification, q` returning `{"items": [ProductSummary], "facets": {...}}`; `GET /api/products/{name}` (404 if missing); `POST /api/access-requests` body `{product, justification, duration}` (justification must be non-empty after trim, else 422; unknown product 404; product with no Entra group 409) returning the `AccessRequest`; `GET /api/access-requests/{number}` (404 if missing).

- [ ] **Step 1: Write failing tests** with `MockTransport` fixtures serving two data products (one fully populated, one with no tables, no tests and no Entra group): list returns both; the empty one has `quality is None`, `table_count == 0`, `entra_group is None`; a view asset is excluded; `GET /api/products?domain=Sales` filters; unknown name 404; POST with whitespace justification 422; POST for the unmapped product 409; POST success returns `REQ0010001` then `REQ0010002`; GET by number round-trips; second call within TTL makes no extra OMD requests.
- [ ] **Step 2: Run** `rtk pytest marketplace/tests -v`. Expected: FAIL.
- [ ] **Step 3: Implement** the service, store and routes. Wire `CatalogService` and the store as app-level singletons created in `main.py` via FastAPI dependencies so tests can override them.
- [ ] **Step 4: Run** same command. Expected: PASS.
- [ ] **Step 5: Commit** `feat(marketplace): catalog API and access requests`.

### Task 5: Seed definitions and writer (users, teams, domains, tags, custom property, data products)

**Files:**
- Create: `marketplace/seed/__init__.py`, `marketplace/seed/definitions.py`, `marketplace/seed/writer.py`, `marketplace/seed/seed.py`, `marketplace/tests/test_seed.py`
- Modify: none

**Interfaces:**
- Consumes: `OmdClient` (Task 2).
- Produces:
  - `definitions.py`: `PRODUCTS: list[ProductDef]` with 7 entries; `ProductDef(name: str, display_name: str, description: str, domain: str, owner: str, steward: str, certification: Literal["Gold","Silver","Bronze"], entra_group: str, tables: list[str], sensitivity_tag: str | None)` where `tables` are existing OMD table FQNs. `USERS: list[UserDef(name, display_name, email)]`, `TEAMS: list[TeamDef(name, display_name)]`, `DOMAINS: list[str]` (Sales, Purchasing, HR plus one more), `ENTRA_PROPERTY = "entraGroup"`. Entra group names follow `GRP-DW-<DOMAIN>-<PRODUCT>-READ`.
  - `writer.py`: `ensure_user`, `ensure_team`, `ensure_domain`, `ensure_classification_tag(classification="Sensitivity", tag="Internal")`, `ensure_custom_property(entity_type="dataProduct", name=ENTRA_PROPERTY)`, `ensure_product(defn: ProductDef) -> str` (creates via `PUT /dataProducts` with owners, experts=[steward], domain, assets, tags, certification, extension). Each `ensure_*` uses PUT-style create-or-update that only sets fields it owns and never touches existing descriptions, tags or glossary terms on tables. `ensure_product` verifies the listed table FQNs exist and raises `SeedError` naming any missing one, creating nothing for that product.
  - `seed.py`: `python -m marketplace.seed.seed` runs users, teams, domains, tag, property, then products, printing one line per entity and a final summary.

- [ ] **Step 1: Pick the tables.** Query OMD for existing AdventureWorks tables (exclude views), choose composition for 7 products over at least 3 domains that matches the names in the design (for example Internet Sales Mart, Purchasing Spend, Employee Directory), and write them into `definitions.py`. Show the product/table/domain list to the user for a quick check before Step 6.
- [ ] **Step 2: Write failing tests** with `MockTransport`: running the seed twice issues only PUT/POST calls that are safe to repeat and produces identical payloads; `ensure_product` with a missing table raises `SeedError` and issues no write; no payload sent for a table contains `description`, `tags` or `columns`; the data product payload includes `extension == {"entraGroup": <group>}`.
- [ ] **Step 3: Run** `rtk pytest marketplace/tests/test_seed.py -v`. Expected: FAIL.
- [ ] **Step 4: Implement** writer and seed per the signatures.
- [ ] **Step 5: Run tests.** Expected: PASS.
- [ ] **Step 6: Run against OMD** `rtk python -m marketplace.seed.seed` twice; the second run must report no changes. Verify in OMD UI that the data products show owners, domain, certification and the Entra group.
- [ ] **Step 7: Commit** `feat(marketplace): seed users, domains and data products`.

### Task 6: Seed PII tags, quality tests and lineage

**Files:**
- Create: `marketplace/seed/quality.py`, `marketplace/seed/lineage.py`, `marketplace/tests/test_seed_quality.py`
- Modify: `marketplace/seed/definitions.py` (add `PII_COLUMNS: dict[str, list[str]]` table FQN to column names, `TESTS: list[TestDef(table: str, name: str, definition: str, parameters: dict, outcome: Literal["Success","Failed"])]`, `LINEAGE: list[tuple[str, str]]` of table FQN pairs), `marketplace/seed/seed.py`

**Interfaces:**
- Consumes: `OmdClient`, `definitions`.
- Produces: `quality.ensure_pii_tags(client)` (adds `PII.Sensitive` to listed columns, appending to existing column tags and never replacing them); `quality.ensure_test(client, defn: TestDef)` creating the test case then posting a result with the stated outcome (`PUT /dataQuality/testCases/{fqn}/testCaseResult`); `lineage.ensure_edges(client, edges)` using `PUT /lineage`. Test outcomes are chosen so product scores are spread: at least one product at 90%+, one at 70-89% and one below 70%, and at least one product with PII.

- [ ] **Step 1: Write failing tests** with `MockTransport`: PII tagging sends a column patch that keeps pre-existing tags; re-running does not create a duplicate test case (existing one is reused and its result re-posted); lineage edge already present is skipped; a missing table raises `SeedError`.
- [ ] **Step 2: Run** `rtk pytest marketplace/tests/test_seed_quality.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** the three modules and call them from `seed.py` after products.
- [ ] **Step 4: Run tests.** Expected: PASS.
- [ ] **Step 5: Run the seed** twice against OMD and check `GET /api/products` (after Task 4's service is running) shows spread quality scores and PII-driven `Confidential` sensitivity on at least one product.
- [ ] **Step 6: Commit** `feat(marketplace): seed PII tags, quality tests and lineage`.

### Task 7: Frontend foundation (design tokens, shell, JS helpers)

**Files:**
- Create: `marketplace/app/static/css/wsbc.css`, `marketplace/app/static/js/util.js`, `marketplace/app/static/js/api.js`, `marketplace/app/static/js/shell.js`, `marketplace/app/static/js/util.test.mjs`
- Modify: `marketplace/app/main.py` (mount `/` static files with `html=True`)

**Interfaces:**
- Produces:
  - `util.js`: `escapeHtml(s: string): string`, `qualityBadge(score: number | null): {label: string, cls: string}` (green 90+, yellow 70-89, red below 70, grey `n/a`), `sensitivityBadge(level): {label, cls}`, `certBadge(cert | null): {label, cls}`.
  - `api.js`: `fetchProducts(filters: object): Promise<{items, facets}>`, `fetchProduct(name): Promise<ProductDetail>`, `createAccessRequest({product, justification, duration}): Promise<AccessRequest>`, `fetchAccessRequest(number)`; any non-2xx throws `ApiError(status, detail)`.
  - `shell.js`: `renderHeader(el)` (WorkSafeBC-style header: orange bottom border, "Data Marketplace", user "John Analyst Doe") and `showBanner(message)` for errors.
  - `wsbc.css`: Bootstrap 5.3.3 variable overrides using the Global Constraints tokens, Noto/Verdana font stack, card, badge, tab and button styles (orange primary, outline variants).

- [ ] **Step 1: Write failing tests** in `util.test.mjs` (`node --test`): `escapeHtml('<img src=x onerror=1>')` contains no `<`; `qualityBadge(90).cls`, `qualityBadge(89)`, `qualityBadge(null).label === "n/a"`; `certBadge(null)` renders a neutral "Uncertified".
- [ ] **Step 2: Run** `rtk node --test marketplace/app/static/js/`. Expected: FAIL.
- [ ] **Step 3: Implement** the JS and CSS.
- [ ] **Step 4: Run** the same command. Expected: PASS. Then start the server (`rtk uvicorn app.main:app --app-dir marketplace --port 8100`) and confirm `/` serves a placeholder page with the header.
- [ ] **Step 5: Commit** `feat(marketplace): design tokens and frontend helpers`.

### Task 8: Search and browse page

**Files:**
- Create: `marketplace/app/static/index.html`, `marketplace/app/static/js/search.js`

**Interfaces:**
- Consumes: `api.fetchProducts`, `util.*`, `shell.*`.
- Produces: page at `/` with the disabled natural-language input (placeholder `Ask in plain English, e.g. "claims data with no personal information" (coming soon)`), a free-text box wired to `q`, five filter groups built from `facets`, result cards (title linking to `/product.html?name=<name>`, certification, sensitivity badge, domain, owner, table count, quality, short description), a result count, an empty state ("No data products match these filters" with a Clear filters button), and the error banner when the API fails. Filter state is mirrored in the URL query string.

- [ ] **Step 1: Write the page and module** per the above, rendering only through `escapeHtml`.
- [ ] **Step 2: Verify in the browser** (Claude in Chrome, at `http://localhost:8100/`): all seeded products appear; each filter narrows results; combining two filters works; a nonsense `q` shows the empty state; stopping OMD shows the banner; the natural-language input cannot be typed in.
- [ ] **Step 3: Commit** `feat(marketplace): search and browse page`.

### Task 9: Data product detail page and request form

**Files:**
- Create: `marketplace/app/static/product.html`, `marketplace/app/static/js/product.js`, `marketplace/app/static/js/request.js`

**Interfaces:**
- Consumes: `api.fetchProduct`, `api.createAccessRequest`, `util.*`.
- Produces: `/product.html?name=<name>` with header (title, certification, domain, owner, steward, quality, sensitivity, Entra group), tabs Overview (description, glossary terms, tags), Datasets (table of dataset name and description), Quality (test results per table), Glossary, Lineage (simple table-level list or small SVG of `lineage.edges`); a "Request access" button opening a modal with business justification (required) and duration (select: 30 days, 90 days, 6 months, 12 months). On submit success it calls `window.open('/snow.html?number=<REQ number>', '_blank')` and shows a confirmation toast. Products with no Entra group show "Not mapped" and a disabled button with an explanatory tooltip. Unknown name shows a not-found message with a link back to `/`.

- [ ] **Step 1: Write the page and modules** per the above.
- [ ] **Step 2: Verify in the browser:** every tab renders for a full product and for the product with no tables/tests (shows empty-state text, no errors in the console); empty justification blocks submit with an inline message; valid submit opens a new tab (the popup must be triggered synchronously from the click, so open the tab first and set its location after the POST resolves); an unknown name shows not found.
- [ ] **Step 3: Commit** `feat(marketplace): data product detail and request form`.

### Task 10: ServiceNow look-alike page

**Files:**
- Create: `marketplace/app/static/snow.html`, `marketplace/app/static/css/snow.css`, `marketplace/app/static/js/snow.js`

**Interfaces:**
- Consumes: `api.fetchAccessRequest`.
- Produces: `/snow.html?number=<REQ number>` styled like standard ServiceNow (dark top banner with a service-portal style navigation, the green "Request submitted" confirmation, a form-style record showing Number, Requested for `John Analyst Doe`, State `Submitted`, Opened (timestamp), Short description `Request access to data product: <title>`, Entra group, Business justification, Duration). It is intentionally static: no workflow steps, no actions. Missing or unknown number shows a ServiceNow-style "Record not found" message. It must not use WorkSafeBC styling so the audience sees a different system.

- [ ] **Step 1: Write the page, stylesheet and module** per the above, escaping all values.
- [ ] **Step 2: Verify in the browser:** submit a request from the detail page; the new tab shows the correct title, user, group, justification and duration; `/snow.html?number=REQ9999999` shows not found.
- [ ] **Step 3: Commit** `feat(marketplace): ServiceNow look-alike request screen`.

### Task 11: Run script, README, end-to-end check

**Files:**
- Create: `marketplace/run.ps1`
- Modify: `marketplace/README.md`

**Interfaces:**
- Produces: `marketplace/run.ps1` which fails with a clear message if `.venv` or `.env` is missing, installs nothing, and starts uvicorn on port 8100 using the repo `.venv`; README covering prerequisites, `seed`, `run`, demo script (search, filter, open detail, request, SNOW tab) and the port.

- [ ] **Step 1: Write `run.ps1` and the README.**
- [ ] **Step 2: Full check:** `rtk pytest marketplace/tests -v` and `rtk node --test marketplace/app/static/js/` pass; run `marketplace/run.ps1`; walk the whole demo flow in the browser end to end, reading the browser console for errors.
- [ ] **Step 3: Confirm the ERD viewer is untouched:** `rtk git status --short` shows no changes under `backend/`, `frontend/`, `tools/`, `scripts/`, or any `erd_*.html`; the ERD viewer's own tests still pass (`rtk pytest backend/tests`).
- [ ] **Step 4: Commit** `docs(marketplace): run script and README`.

---

## Self-review

- **Spec coverage:** search with disabled NL box and five filters (Tasks 3, 4, 8); rich metadata and Datasets table (Tasks 4, 9); request with justification and duration (Tasks 4, 9); new-tab SNOW look-alike with Entra group (Task 10); WorkSafeBC look (Task 7); seed of owners, stewards, quality, PII, glossary terms, certification, Entra property, lineage (Tasks 5, 6); ERD viewer untouched (Task 11 step 3); capability verification gate (Task 1). Glossary terms on products come from existing glossary tagging on tables and any `Glossary` tags on products; no new glossary seeding is planned.
- **Type consistency:** `ProductSummary`, `ProductDetail`, `AccessRequest`, `OmdClient`, `ensure_*` names are used identically across tasks.
- **Open for the user:** the product/table/domain composition (Task 5, Step 1) is shown for a quick check before seeding.
