# AdventureWorks Business Glossary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate an OMD-importable business glossary, a term-to-object mapping and a term-relationship file for AdventureWorks2019 and AdventureWorksDW2019 from the metadata ingested in OMD.

**Architecture:** A small stdlib-only Python package (`tools/glossary/`) pulls a read-only snapshot of tables, columns and constraints from the OMD API, loads hand-curated term data (JSON, one file per domain), validates it against the snapshot, and writes four files to `docs/glossary/`. Curated data is the source of truth; the CSVs are regenerated from it.

**Tech Stack:** Python 3.12 (repo `.venv`), `urllib`, `csv`, `json`, pytest.

**Spec:** `docs/superpowers/specs/2026-10-24-adventureworks-glossary-design.md`

## Global Constraints

- OMD is the only source; no SQL Server connection. OMD 2.0.5 at `OMD_HOST` (already ends in `/api`; paths are `{OMD_HOST}/v1/...`). Token is `OMD_TOKEN`, both read from the git-ignored `.env`; never print or log the token.
- Only read-only GET calls, plus the dry-run import in Task 7 (`dryRun=true`). Nothing is written to OMD.
- Scope: service `MSSQL Desktop`, databases `AdventureWorks2019` and `AdventureWorksDW2019` only (not `master`, `WideWorldImporters`).
- Glossary name: `AdventureWorks Business Glossary`. Term FQN is `AdventureWorks Business Glossary.<Parent>.<Name>` (root terms: `AdventureWorks Business Glossary.<Name>`).
- CSV columns, in order: `parent,name,displayName,description,synonyms,relatedTerms,references,tags,reviewers,owner,glossaryStatus,color`. Multi-value cells are joined with `;`. `relatedTerms` entries are `relationType:termFQN`; valid types: `relatedTo, synonym, broader, narrower, antonym, partOf, hasPart`. `parent` is the parent term FQN, empty at root; parents precede children.
- `glossaryStatus` is `Approved` for terms with Microsoft-sourced definitions and `Draft` for inferred ones (all warehouse-derived terms). `reviewers`, `owner`, `tags`, `references`, `color` stay empty.
- Domains (root terms): Sales, Production, Purchasing, Human Resources, People and Contacts, Analytics (Data Warehouse). Business concepts, not one term per table: 80 to 120 terms.
- Excluded tables: `DatabaseLog`, `ErrorLog`, `sysdiagrams`, `AWBuildVersion`, `AdventureWorksDWBuildVersion` (and `DatabaseLog` in DW).
- Run everything from the repo root with `.venv/Scripts/python.exe`. Commands in the shell are prefixed with `rtk` per the user's global instructions.
- Commits are conventional-commit style (`feat:`, `docs:`, `test:`).

## Review Focus

- Descriptions with commas, double quotes, newlines and Markdown must survive the CSV round trip (Task 3).
- A term or object name containing a `.` would corrupt OMD FQNs; validation must reject term names with a dot (Task 2).
- A table renamed or removed in OMD after curation must produce a validation error naming the table, not a silent drop (Task 2).
- A missing or rejected token (HTTP 401/403) or unreachable OMD must give a one-line error, not a traceback, and never echo the token (Task 1).
- `relatedTerms` pointing to a term that does not exist would make OMD reject the whole import; validation must catch it before the file is written (Task 2).

---

## File Structure

- `tools/glossary/omd_client.py`: OMD HTTP access (snapshot fetch, `.env` loading, dry-run import).
- `tools/glossary/model.py`: term dataclass, loading curated data, FQN helpers, validation.
- `tools/glossary/writers.py`: the three CSV writers.
- `tools/glossary/build.py`: CLI (`snapshot`, `check`, `build`) wiring the above.
- `tools/glossary/data/terms/*.json`: curated terms, one file per domain.
- `tools/glossary/data/relationships.json`: curated term-to-term relations.
- `tools/glossary/data/exclusions.json`: excluded tables with reasons.
- `tools/glossary/tests/`: pytest tests.
- `docs/glossary/`: generated outputs and README.
- `.gitignore`: add `tools/glossary/.cache/` (snapshot cache).

---

### Task 1: OMD client and snapshot

**Files:**
- Create: `tools/glossary/__init__.py`, `tools/glossary/omd_client.py`, `tools/glossary/tests/__init__.py`, `tools/glossary/tests/test_omd_client.py`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `load_env(path: Path) -> dict[str, str]` (parses `KEY=VALUE` lines, ignores comments/blank lines, strips surrounding quotes).
- Produces: `class OmdError(Exception)` (message safe to print).
- Produces: `fetch_snapshot(get_json: Callable[[str], dict]) -> dict` returning `{"service": "MSSQL Desktop", "databases": {"AdventureWorks2019": [table, ...], "AdventureWorksDW2019": [...]}}` where each table is the OMD table JSON with `columns`, `tableConstraints`, `description`, `tableType`, `fullyQualifiedName`.
- Produces: `make_get_json(host: str, token: str) -> Callable[[str], dict]` (GET with bearer token; maps HTTP 401/403 and connection failures to `OmdError`).

- [ ] **Step 1: Write failing tests** in `test_omd_client.py`:
  - `test_load_env_parses_pairs_and_skips_comments` (input `# c\nOMD_HOST=http://x/api\nOMD_TOKEN="abc"\n` gives `{"OMD_HOST": "http://x/api", "OMD_TOKEN": "abc"}`).
  - `test_fetch_snapshot_follows_paging`: a fake `get_json` returns two pages for AdventureWorks2019 (`paging.after` set on page one, absent on page two) and one page for the DW; assert all tables are collected and the request URLs contain `database=MSSQL%20Desktop.AdventureWorks2019` and `fields=columns%2Cdescription%2CtableConstraints`.
  - `test_make_get_json_maps_401_to_omd_error_without_token`: patch `urllib.request.urlopen` to raise `HTTPError(401)`; assert `OmdError` is raised and `"secret-token"` is not in `str(exc)`.
- [ ] **Step 2: Run to verify failure**: `rtk .venv/Scripts/python.exe -m pytest tools/glossary/tests/test_omd_client.py -v`. Expected: FAIL (ImportError).
- [ ] **Step 3: Implement** the three functions in `omd_client.py` (stdlib `urllib`, page size 100, follow `paging.after`). Add `tools/glossary/.cache/` to `.gitignore`.
- [ ] **Step 4: Run tests**: same command. Expected: 3 passed.
- [ ] **Step 5: Commit**: `rtk git add tools .gitignore && rtk git commit -m "feat: add OMD client and snapshot fetch for glossary tooling"`

### Task 2: Term model and validation

**Files:**
- Create: `tools/glossary/model.py`, `tools/glossary/tests/test_model.py`

**Interfaces:**
- Consumes: snapshot shape from Task 1.
- Produces: `GLOSSARY_NAME = "AdventureWorks Business Glossary"`, `SERVICE = "MSSQL Desktop"`, `RELATION_TYPES = ("relatedTo","synonym","broader","narrower","antonym","partOf","hasPart")`.
- Produces: `@dataclass Term` with fields `name: str`, `parent: str | None`, `status: str`, `description: str`, `synonyms: list[str]`, `related: list[dict]` (`{"type","term"}` where `term` is a term path like `Sales.Sales Order`), `objects: list[str]` (`<db>.<schema>.<table>`), `columns: list[str]` (`<db>.<schema>.<table>.<column>`), `basis: str` (`name|fk|judgment|view`); properties `path` (`name` or `parent.name`) and `fqn` (`GLOSSARY_NAME.path`).
- Produces: `load_terms(data_dir: Path) -> list[Term]` (reads every `terms/*.json`, each a JSON list of objects with the field names above; missing optional lists default to empty) and `load_exclusions(data_dir: Path) -> dict[str, str]` (`<db>.<schema>.<table>` to reason).
- Produces: `validate(terms: list[Term], snapshot: dict, exclusions: dict[str,str], schemas: set[str] | None = None) -> list[str]` returning human-readable error strings; empty list means valid. When `schemas` is given, the coverage rule only checks tables in those `<db>.<schema>` names (used while curating incrementally).
- Produces: `object_fqn(short: str) -> str` (prefixes `SERVICE.`).

- [ ] **Step 1: Write failing tests**, one per rule, using a tiny hand-built snapshot (two tables in `AdventureWorks2019.Sales`, one in `AdventureWorksDW2019.dbo`) and these names/assertions (each asserts the error list contains a substring):
  - `test_valid_data_has_no_errors`
  - `test_duplicate_path_is_reported` ("duplicate")
  - `test_dot_in_term_name_is_rejected` ("contains a dot")
  - `test_missing_parent_is_reported` ("parent")
  - `test_parent_must_be_root` (hierarchy is two levels only)
  - `test_invalid_status_is_reported` ("status")
  - `test_approved_term_needs_operational_object` (a term mapping only DW objects but marked `Approved` fails; DW-only must be `Draft`)
  - `test_non_root_term_needs_an_object` ("no objects")
  - `test_unknown_object_names_the_table` (error contains the missing `AdventureWorks2019.Sales.Gone`)
  - `test_unknown_column_is_reported`
  - `test_related_term_must_exist` and `test_related_type_must_be_valid`
  - `test_unmapped_table_is_reported_unless_excluded`
  - `test_schemas_filter_limits_coverage_check`
- [ ] **Step 2: Run to verify failure**: `rtk .venv/Scripts/python.exe -m pytest tools/glossary/tests/test_model.py -v`. Expected: FAIL (ImportError).
- [ ] **Step 3: Implement** `model.py`. Coverage rule: every table in the snapshot (both databases) is either referenced by some term's `objects` or present in `exclusions`.
- [ ] **Step 4: Run tests**: same command. Expected: all passed.
- [ ] **Step 5: Commit**: `rtk git add tools && rtk git commit -m "feat: add glossary term model and validation"`

### Task 3: CSV writers

**Files:**
- Create: `tools/glossary/writers.py`, `tools/glossary/tests/test_writers.py`

**Interfaces:**
- Consumes: `Term`, `GLOSSARY_NAME`, `object_fqn` from Task 2; snapshot from Task 1.
- Produces: `write_glossary_csv(terms: list[Term], path: Path) -> None`: one row per term, roots first then children (stable order within each), columns exactly as in Global Constraints; `parent` is the parent term FQN; `displayName` equals `name`; `synonyms` joined with `;`; `relatedTerms` as `type:fqn` joined with `;`.
- Produces: `write_mapping_csv(terms: list[Term], path: Path) -> None` with header `term_fqn,object_type,object_fqn,basis` (`table` rows from `objects`, `column` rows from `columns`).
- Produces: `derive_fk_relations(terms: list[Term], snapshot: dict) -> list[dict]` returning `{"subject","relation":"references","object","evidence"}` rows (term FQNs) for each FK between mapped tables whose terms differ, de-duplicated by (subject, object).
- Produces: `write_relationships_csv(curated: list[dict], derived: list[dict], path: Path) -> None` with header `subject,relation,object,evidence,source`; curated rows have `source=curated` and win over a derived row with the same (subject, object).
- Files are written UTF-8, `newline=""`, via the `csv` module.

- [ ] **Step 1: Write failing tests**:
  - `test_glossary_csv_round_trips_awkward_text`: a description with a comma, a `"` and a newline plus Markdown (`**bold**`) is read back identically with `csv.DictReader`.
  - `test_roots_precede_children_and_parent_is_fqn`
  - `test_related_terms_are_typed_and_semicolon_joined` (e.g. `partOf:AdventureWorks Business Glossary.Sales.Sales Order;relatedTo:...`)
  - `test_header_matches_omd_columns` (exact header list from Global Constraints)
  - `test_mapping_csv_has_table_and_column_rows`
  - `test_derive_fk_relations_skips_same_term_and_dedupes`
  - `test_curated_relation_overrides_derived`
- [ ] **Step 2: Run to verify failure**: `rtk .venv/Scripts/python.exe -m pytest tools/glossary/tests/test_writers.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** the four functions. For `derive_fk_relations`, build a table-FQN-to-term-FQNs map from `objects`; an FK's referred table FQN is the `referredColumns[0]` with the last segment removed; evidence is `fk: <table fqn>.<column> -> <referred column>`.
- [ ] **Step 4: Run tests**: same command. Expected: all passed.
- [ ] **Step 5: Commit**: `rtk git add tools && rtk git commit -m "feat: add glossary, mapping and relationship CSV writers"`

### Task 4: CLI and first real snapshot

**Files:**
- Create: `tools/glossary/build.py`, `tools/glossary/tests/test_build.py`, `tools/glossary/data/terms/.gitkeep`, `tools/glossary/data/exclusions.json`

**Interfaces:**
- Consumes: everything from Tasks 1 to 3.
- Produces: `main(argv: list[str] | None = None) -> int` with subcommands: `snapshot` (fetch to `tools/glossary/.cache/snapshot.json`), `check [--schemas A,B]` (load data and snapshot, run `validate`, print errors one per line, return 1 if any), `build` (run `check`, then write the four-file output set into `docs/glossary/`; refuses to write if validation fails). Error from `OmdError` prints one line and returns 2.
- `exclusions.json` is `{"AdventureWorks2019.dbo.DatabaseLog": "technical audit log", ...}` for the excluded tables in Global Constraints (include `AdventureWorks2019.dbo.ErrorLog`, `AdventureWorks2019.dbo.AWBuildVersion`, `AdventureWorksDW2019.dbo.DatabaseLog`, `AdventureWorksDW2019.dbo.sysdiagrams`, `AdventureWorksDW2019.dbo.AdventureWorksDWBuildVersion`).

- [ ] **Step 1: Write failing tests**: `test_check_returns_1_and_lists_errors_for_invalid_data` and `test_build_writes_nothing_when_invalid` (tmp dirs, a pre-written tiny snapshot file, `main(["check", ...])` with path overrides via `--data-dir`, `--snapshot`, `--out-dir` options), and `test_omd_error_prints_one_line_and_returns_2`.
- [ ] **Step 2: Run to verify failure**: `rtk .venv/Scripts/python.exe -m pytest tools/glossary/tests/test_build.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `build.py` and `exclusions.json`.
- [ ] **Step 4: Run all tests**: `rtk .venv/Scripts/python.exe -m pytest tools/glossary -v`. Expected: all passed.
- [ ] **Step 5: Take the real snapshot**: `rtk .venv/Scripts/python.exe -m tools.glossary.build snapshot`. Expected: one line reporting 93 tables for AdventureWorks2019 and 37 for AdventureWorksDW2019. If the numbers differ, stop and tell the owner.
- [ ] **Step 6: Commit**: `rtk git add tools && rtk git commit -m "feat: add glossary build CLI"`

### Task 5: Curate AdventureWorks2019 terms, Sales and Purchasing

**Files:**
- Create: `tools/glossary/data/terms/sales.json`, `tools/glossary/data/terms/purchasing.json`

**Interfaces:**
- Consumes: `Term` JSON shape from Task 2; real snapshot from Task 4.
- Produces: root terms `Sales` and `Purchasing`, plus their concept terms, all `Approved`, covering every `AdventureWorks2019.Sales.*` and `AdventureWorks2019.Purchasing.*` table and view (views map to the concept they report on with `basis: "view"`).

- [ ] **Step 1: Read the real descriptions** for these schemas from `tools/glossary/.cache/snapshot.json` (table and column descriptions, FKs) before authoring.
- [ ] **Step 2: Author the two files.** Group tables into business concepts (for example Sales Order covering `SalesOrderHeader`, `SalesOrderDetail`, `SalesOrderHeaderSalesReason`; Customer; Sales Territory; Sales Person; Special Offer; Currency; Credit Card; Shopping Cart; Vendor; Purchase Order; Ship Method; Product Vendor). Definitions are adapted from the OMD descriptions to describe the concept, not the table. Add `synonyms` where natural and `related` using the typed vocabulary (for example Sales Order Line `partOf` Sales Order). Terms use two levels only.
- [ ] **Step 3: Check coverage**: `rtk .venv/Scripts/python.exe -m tools.glossary.build check --schemas AdventureWorks2019.Sales,AdventureWorks2019.Purchasing`. Expected: no errors. (Other schemas' tables are not yet checked; `related` may only point to terms that exist.)
- [ ] **Step 4: Commit**: `rtk git add tools && rtk git commit -m "feat: add Sales and Purchasing glossary terms"`

### Task 6: Curate AdventureWorks2019 terms, Production, Human Resources, People and Contacts

**Files:**
- Create: `tools/glossary/data/terms/production.json`, `tools/glossary/data/terms/human-resources.json`, `tools/glossary/data/terms/people.json`

**Interfaces:**
- Consumes/Produces: as Task 5, for the schemas `Production`, `HumanResources`, `Person`. The stray `AdventureWorks2019.dbo.Person` maps to People if its columns match `Person.Person`, otherwise it goes in `exclusions.json` with a reason.

- [ ] **Step 1: Read the real descriptions** for these schemas and for `AdventureWorks2019.dbo.Person` from the snapshot.
- [ ] **Step 2: Author the three files** following the Task 5 rules (examples: Product, Product Category, Bill of Materials, Work Order, Inventory, Product Model, Product Review; Employee, Department, Shift, Pay History, Job Candidate; Person, Address, Contact Type, Email Address, Phone Number, Country/Region, State/Province). Cross-domain `related` links use the full path (for example `People and Contacts.Address`).
- [ ] **Step 3: Check coverage**: `rtk .venv/Scripts/python.exe -m tools.glossary.build check --schemas AdventureWorks2019.Production,AdventureWorks2019.HumanResources,AdventureWorks2019.Person,AdventureWorks2019.dbo`. Expected: no errors.
- [ ] **Step 4: Commit**: `rtk git add tools && rtk git commit -m "feat: add Production, HR and People glossary terms"`

### Task 7: Curate warehouse terms

**Files:**
- Create: `tools/glossary/data/terms/analytics.json`

**Interfaces:**
- Consumes: terms from Tasks 5 and 6 (for `related` links such as `DimCustomer`'s term `relatedTo` Customer).
- Produces: root term `Analytics (Data Warehouse)` (`Draft`) and Draft concept terms for the warehouse tables (Dimension, Fact and the concrete ones such as Internet Sales Fact, Reseller Sales Fact, Date Dimension, Call Center, Survey Response, Financial Reporting, Scenario, Account, Organization, Department Group, Prospective Buyer). Warehouse tables that duplicate an operational concept are also added to that operational term's `objects` with `basis: "name"` (for example `DimCustomer` under Customer), keeping that term `Approved`. Warehouse-only terms have a description that states the definition is inferred from naming and structure.

- [ ] **Step 1: Read the DW table and column names and FKs** from the snapshot (no descriptions exist).
- [ ] **Step 2: Author `analytics.json` and add the DW objects to the operational terms** in the files from Tasks 5 and 6.
- [ ] **Step 3: Check full coverage**: `rtk .venv/Scripts/python.exe -m tools.glossary.build check`. Expected: no errors; term count between 80 and 120 (print it from `check`; if outside the range, tell the owner rather than padding or cutting).
- [ ] **Step 4: Commit**: `rtk git add tools && rtk git commit -m "feat: add warehouse glossary terms"`

### Task 8: Relationships, generated outputs, README and dry-run import

**Files:**
- Create: `tools/glossary/data/relationships.json`, `docs/glossary/README.md`, generated `docs/glossary/adventureworks-glossary.csv`, `docs/glossary/term-object-mapping.csv`, `docs/glossary/term-relationships.csv`
- Modify: `tools/glossary/omd_client.py`, `tools/glossary/build.py`, `tools/glossary/tests/test_omd_client.py`

**Interfaces:**
- Produces: `dry_run_import(host: str, token: str, glossary: str, csv_text: str) -> dict` in `omd_client.py`: `PUT {host}/v1/glossaries/name/{glossary}/import?dryRun=true`, `Content-Type: text/plain`, returns the parsed JSON; errors as `OmdError`.
- Produces: `build.py` subcommand `dry-run` that posts `docs/glossary/adventureworks-glossary.csv` and prints the OMD result summary (rows processed, passed, failed, and any per-row failure message).
- `relationships.json` is a list of `{"subject","relation","object","evidence"}` using term FQNs and domain-specific relation names (for example `placed by`, `belongs to`, `supplied by`), covering the main concepts' relations that OMD's vocabulary cannot express.

- [ ] **Step 1: Write failing test** `test_dry_run_import_sends_put_with_text_plain_and_dry_run_flag` (patch `urlopen`, assert method, URL query, header, body).
- [ ] **Step 2: Run to verify failure**: `rtk .venv/Scripts/python.exe -m pytest tools/glossary/tests/test_omd_client.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `dry_run_import` and the `dry-run` subcommand.
- [ ] **Step 4: Run tests**: `rtk .venv/Scripts/python.exe -m pytest tools/glossary -v`. Expected: all passed.
- [ ] **Step 5: Author `relationships.json`**, review the derived FK relations printed by `build`, and curate labels for the important pairs.
- [ ] **Step 6: Generate outputs**: `rtk .venv/Scripts/python.exe -m tools.glossary.build build`. Expected: validation passes and the three CSVs appear in `docs/glossary/`.
- [ ] **Step 7: Write `docs/glossary/README.md`**: what each file is, how the glossary is built (curated data, regenerate command), the Approved/Draft meaning, the excluded tables, and the import steps (create empty glossary named `AdventureWorks Business Glossary`, then Glossary page, Import).
- [ ] **Step 8: Commit**: `rtk git add tools docs/glossary && rtk git commit -m "feat: generate AdventureWorks glossary files"`
- [ ] **Step 9: Hand over to the owner.** Ask them to create the empty glossary in the OMD UI (or approve creating it via API). Once it exists, run `rtk .venv/Scripts/python.exe -m tools.glossary.build dry-run` and report the result. Fix any row OMD rejects (likely FQN quoting for names with spaces or special characters) by adjusting the writers, re-running `build`, and committing. The owner then runs the real import in the UI; nothing is imported by the tooling.
