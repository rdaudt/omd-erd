# Data Marketplace Demo: Design

## Intent and why

Today, getting access to a data warehouse dataset means asking the Data Engineering (DE) team by Teams or email, waiting for a DE representative to name the right MS Entra group, then submitting a ServiceNow (SNOW) membership request that runs an approval workflow. The pain points are (1) there is no marketplace where people can browse curated datasets, and (2) a human must tell each requester which Entra group to ask for.

We are rolling out OpenMetadata (OMD). The vision is a data marketplace built as a custom app on top of the OMD and SNOW APIs: users find a data product in OMD, request access from there, and OMD triggers the existing SNOW workflow. A mapping from each data product to the Entra group that grants access removes the human middleman.

This project is a **demo for leadership**, not the real integration. The moments that must land: (a) the richness of metadata on each data product, and (b) a more efficient access workflow with no human handing out group names.

## Goals

- A new, standalone **Data Marketplace web app** that reads from the local OMD instance via its API.
- **Search and browse** curated data products.
- **Explore** rich metadata of a data product and of the datasets (tables) inside it.
- **Request access** to a data product, which opens a **ServiceNow look-alike** screen in a new browser tab.
- Look and feel follows the **WorkSafeBC UX design system**; Informatica's cloud marketplace is the inspiration for the browsing experience.
- Seed OMD with the metadata needed to make the demo rich (this is part of the work).

## Non-goals

- No real SNOW integration, no real Entra group changes, no real authentication.
- No admin screen, no shopping cart, no "My requests" page.
- Natural-language search is **not implemented**; only a disabled input showing a placeholder.
- No approval workflow simulation: the SNOW look-alike is a single screen.
- Selecting individual datasets for access is out: access is requested for a whole data product.

## Anti-goals

- The existing **ERD viewer app** (`backend/`, `frontend/` and the `erd_*.html` files) must not be changed or interfered with in any way. The new app lives in its own folder with its own run command and port.
- The demo must not look like a mock-up of something fake: metadata shown must come live from OMD, not from hard-coded page content.

## Constraints

- Source of truth for catalog content is the local OMD instance (see the project README and `docs/RUNBOOK.md` for how to run it).
- The OMD API token must stay on the server side; the browser never sees it.
- Must run on a laptop with one start command, nothing to compile.
- The "unit" in the marketplace is the OMD **data product**. Tables inside it are its assets.

## What the user sees

**Persona:** a fixed, static user, "John Analyst Doe". No login, no persona switcher.

**Search and browse page**
- Natural-language search input at the top, disabled, with a placeholder along the lines of "Ask in plain English, e.g. 'claims data with no personal information' (coming soon)".
- Filters: domain, sensitivity, quality score, owner, certification.
- Result cards showing: title, certification badge, PII/sensitivity badge, domain, owner, number of tables, quality score, short description.

**Data product detail page**
- Header: title, certification, domain, owner, steward, quality score, sensitivity/PII flag.
- Tabs: Overview, Datasets, Quality, Glossary, Lineage.
- Overview: description, glossary terms, tags, other metadata.
- Datasets tab: a table with **dataset name** and **description** for each table in the data product.
- A "Request access" button.

**Request access**
- A form asking for **business justification** and **duration**.
- On submit, a **new browser tab** opens with the SNOW look-alike (so the audience sees the switch between systems).

**ServiceNow look-alike**
- Styled like standard ServiceNow UI.
- States that a request has been submitted for access to the data product `[data product title]` for user `John Analyst Doe`.
- Shows the **Entra group** that the request maps to, plus the justification and duration entered.
- Static: no real workflow steps are played out.

## Data and mapping

- About **7 to 8 data products** across a few business domains (for example Sales, Purchasing, HR), built from the existing AdventureWorks tables in OMD. Tables that are views are not used unless asked.
- Metadata to add in OMD as part of this work: owners and stewards, descriptions, data quality tests, PII/sensitivity tags, glossary terms, certification, and a custom property **"Entra group"** on each data product.
- The data product to Entra group mapping lives in that OMD custom property, and the SNOW look-alike reads it from there.

## Decided how-it-gets-made

- **Frontend (decided by the user, with a recommendation from me):** plain HTML, CSS and JavaScript (ES modules) on Bootstrap 5.3; no React, no build step. Served by the backend.
- **Design system:** the WorkSafeBC design system (v8.1.0) is Bootstrap 5.3 plus its own layer. Documented values: orange `#ED8B00`, body copy `#453F39`, warm greys (`#F1F0EF`, `#E4E2E0`, `#C9C5C1`, `#ADA8A2`, `#47423C`), accents (mountain blue `#6399AE`, huckleberry red `#A4343A`, sunset orange `#DC4405`, sunrise yellow `#F1BE48`, moss green `#888D30`), Noto body font with Verdana fallback, Halis headings, Font Awesome 4.7 icons, fixed (1140px) or fluid layout. Reference sites: https://ux-static.online.worksafebc.com/ and https://ux.online.dv.worksafebc.com/. The official `wsbc.css` may not be reachable, so the look is rebuilt from these documented values.
- **Backend (my call):** a small Python (FastAPI) service that proxies and shapes OMD API responses for the frontend, and serves the static frontend and the SNOW look-alike page.
- **Product-level quality score (my call):** the average across the tables in the data product.
- **Certification (my call):** OMD's built-in certification tags.

## Left to the builder

- Folder name and run command, API route design, how filters are implemented (server side or client side).
- Exact seeding mechanism (script using the OMD API is expected, and it should be re-runnable).
- Exact visual details of cards and pages within the design system and the sketches agreed in brainstorming.
- The fake ServiceNow look-alike's exact fields, as long as it is recognizably standard ServiceNow UI and shows the items listed above.

## Further calls made by me (not yet confirmed by the user)

- **Table quality score:** pass rate of the table's OMD test cases (0 to 100%). Seeding must include some deliberately failing tests so scores vary. Filter buckets: 90%+, 70-89%, below 70%. The Quality tab lists the test cases and their latest result per table.
- **Sensitivity:** derived at the data product level as the highest level among its tables' and columns' tags. Levels: Public, Internal, Confidential (contains PII). Filter and badges use these three.
- **Owners and stewards:** fabricated OMD users and teams created by the seed. Steward is stored as an OMD expert on the data product.
- **Entra group:** also shown on the detail page, since it supports the "no human hands out group names" story.
- **Lineage tab:** table-level only, drawn as a simple list or small SVG without a build step; lineage is seeded if missing.
- **Existing OMD content:** the seed is additive and idempotent. It never overwrites existing descriptions, tags or glossary terms on tables.
- **OMD connection:** the backend reads the OMD URL and token from environment variables, reusing the ERD backend's existing configuration values read-only (without importing or modifying its code).
- **To verify first in the plan:** that OMD 2.0.5 supports custom properties on data products, assigning tables to a data product, and certification via the API. If custom properties on data products are unsupported, stop and bring the fallback to the user.

## Open items

- Which AdventureWorks tables compose each data product and which domains to use are to be chosen by the builder and shown to the user for a quick check.
