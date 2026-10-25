# AdventureWorks Business Glossary: Design

Date: 2026-10-24

## Intent and why

The local OpenMetadata (OMD 2.0.5, `http://localhost:8585`) holds ingested metadata for two SQL Server sample databases: `AdventureWorks2019` (OLTP) and `AdventureWorksDW2019` (data warehouse). Both sit under the service `MSSQL Desktop`.

The owner wants a single business glossary covering both databases, generated from the ingested metadata instead of written by hand. The glossary is the first of three steps:

1. **This work:** produce the glossary in a form that can be uploaded to OMD.
2. **Next:** assign glossary terms to database objects (tables and columns) in OMD.
3. **After that:** derive an ontology from the glossary.

The owner will also use the glossary to demonstrate to others how glossary exploration works in OMD. Steps 2 and 3 shape the design: every term should be taggable to real objects, and relationships between terms should be captured in a way an ontology can later consume.

## Goals

- One glossary, `AdventureWorks Business Glossary`, loadable through OMD's glossary CSV import.
- Business-level concepts, not one term per table. Roughly 80 to 120 terms.
- A two-level hierarchy: domain terms at the root, concepts beneath them.
- Terms whose definitions are traceable to OMD descriptions or, for the warehouse, clearly marked as inferred.
- A term-to-object mapping file so the tagging step is mechanical.
- Relationships between terms, typed where possible, to seed the ontology step.
- The generation is a repeatable script, so the output can be regenerated after edits.

## Non-goals

- Writing anything to OMD without the owner's review of the output first. The deliverable is files; the owner uploads or approves a push.
- Tagging database objects with terms (step 2).
- Building the ontology (step 3).
- Covering `master` or `WideWorldImporters`, which are also ingested in OMD.
- One term per table or per column.

## Anti-goals (failure even if it technically works)

- A glossary that is a rename of the table list.
- Inferred warehouse definitions presented as authoritative.
- Terms that cannot be mapped to any database object, or mappings that point to objects that do not exist in OMD.
- A CSV that OMD rejects or half-imports.

## Source data (verified 2026-10-24)

OMD is the only source. The owner confirmed there is no further metadata for the warehouse in SQL Server, so no database connection is needed.

| | AdventureWorks2019 | AdventureWorksDW2019 |
|---|---|---|
| Tables, including views | 93 (Person 15, Production 28, Sales 26, HumanResources 13, Purchasing 7, dbo 4) | 37, all in dbo (Dim*, Fact*, views) |
| Table descriptions | 91 of 93 | 0 |
| Column descriptions | 485 of 761 | 0 |
| Foreign keys | 90 | 44 |

A snapshot of the tables, columns, descriptions and constraints was pulled with read-only API calls and saved at `scratchpad/omd_tables.json`. The generator script should re-pull it from the API. The token and host come from the git-ignored `.env` (`OMD_TOKEN`, `OMD_HOST`). Note that `OMD_HOST` already ends in `/api`.

## Decisions made with the owner

- **One glossary** for both databases.
- **Hierarchy by business domain:** Sales, Production, Purchasing, Human Resources, People and Contacts, plus a sixth domain, Analytics (Data Warehouse), for warehouse-only concepts such as Dimension, Fact, Date and Fiscal Calendar, Call Center, Financial Reporting and Survey Response.
- **Business concepts, not tables.** Junction, history and technical tables fold into the concept they serve. `DatabaseLog`, `ErrorLog`, `sysdiagrams` and the build-version tables are excluded.
- **Warehouse terms map to operational terms**, for example `DimCustomer` to Customer and `FactInternetSales` to Sales Order.
- **Status:** terms whose definitions come from Microsoft's OMD descriptions are `Approved`. Terms whose definitions are inferred (all warehouse-derived ones) are `Draft`.
- **Side files:** a term-to-object mapping and a typed-relationships file, alongside the CSV.

## Constraints from OMD 2.0.5

Checked against `GET /v1/glossaries/documentation/csv`:

- Import goes into an **existing** glossary. None exists yet, so it must be created first, empty. Creating it is a write to OMD and needs the owner's go-ahead (the UI takes seconds).
- CSV columns: `parent, name*, displayName, description, synonyms, relatedTerms, references, tags, reviewers, owner, glossaryStatus, color`. Only `name` is required. The column is `owner`, not `owners`.
- `parent` is the fully qualified name of the parent term, empty at the root. Parents must appear before their children.
- `relatedTerms` takes `relationType:termFQN` entries separated by `;`. Valid relation types are `relatedTo`, `synonym`, `broader`, `narrower`, `antonym`, `partOf`, `hasPart`. A bare FQN defaults to `relatedTo`.
- Descriptions are Markdown.

## What the generator produces

Output directory: `docs/glossary/` (committed, so the owner can review diffs).

1. `adventureworks-glossary.csv`: the upload file. Typed `relatedTerms` use the vocabulary above. `partOf` and `hasPart` are used for composition, such as Sales Order Line part of Sales Order. Foreign-key-derived links that do not fit the vocabulary use `relatedTo`.
2. `term-object-mapping.csv`: one row per term-to-object pair, with the term FQN, the object type (table or column), the object FQN, and the basis for the link (name match, foreign key, or judgment).
3. `term-relationships.csv`: subject term, relation, object term, evidence. This keeps domain-specific relations that OMD's vocabulary cannot express, such as "Sales Order placed by Customer", for the ontology step.
4. `README.md`: how to create the glossary, import the CSV, and what the status values mean.

A validation step runs before the files are handed over and fails loudly on: duplicate term names, a missing parent, a parent listed after its child, empty `name`, an invalid relation type, a status other than `Draft`/`Approved`, or a mapped object FQN that is not in the OMD snapshot. Every in-scope table must either map to a term or be on the explicit exclusion list.

## Approach to term definition

The term list is curated judgment, not mechanical output. The script reads OMD, but which concepts exist, how tables group into them, and the wording of definitions are decided by reading the schemas. The curated term list is kept as a checked-in data file (term, domain, definition source, mapped tables) that the script turns into the three outputs. Edits go to that file, and the CSVs are regenerated.

Definitions for Approved terms are adapted from the OMD table and column descriptions so they describe the business concept, not the table. Draft terms say in the description that the definition is inferred from naming and structure, not from source documentation.

## Left to the builder

- The exact term list and wording (the owner will review).
- Script language and layout; the repo has a Python backend and a `.venv`, so Python is the natural fit.
- Whether to also offer pushing terms through the API after review. The default is no.
- `color`, `owner` and `reviewers` columns stay empty unless the owner asks.

## Calls made without the owner (to check while reading)

- Glossary name: "AdventureWorks Business Glossary".
- Output location `docs/glossary/` and committing the curated data file.
- Excluding the technical tables listed above.
- Python for the generator.
- Views (`v*`) map to the same term as the tables they report on, and appear in the mapping file with basis "view".
- The stray `dbo.Person` in AdventureWorks2019 (not in the standard sample) is mapped to the People term if it matches `Person.Person`, otherwise excluded and listed in the README.
- Warehouse tables with no operational equivalent (`FactCallCenter`, `FactSurveyResponse`, `ProspectiveBuyer`, `DimAccount`, `FactFinance`, `DimScenario`, `DimOrganization`, `DimDepartmentGroup`) become terms under Analytics (Data Warehouse), as Draft.
