# AdventureWorks Business Glossary

A business glossary for the two AdventureWorks databases ingested in OpenMetadata
(`MSSQL Desktop`: `AdventureWorks2019` and `AdventureWorksDW2019`), generated from the
metadata in OMD. Design: `docs/superpowers/specs/2026-10-24-adventureworks-glossary-design.md`.

## Files

| File | Purpose |
|---|---|
| `adventureworks-glossary.csv` | **Import pass 1.** Every term (one glossary, six domains, business concepts beneath them) with the `relatedTerms` column empty. |
| `adventureworks-glossary-relations.csv` | **Import pass 2.** The same terms with `relatedTerms` filled in (typed: `partOf`, `hasPart`, `narrower`, `relatedTo`...). Import it after pass 1 so every related term already exists. |
| `term-object-mapping.csv` | Term to table/column pairs (`term_fqn, object_type, object_fqn, basis`) for the next step, tagging objects with terms. `basis` is `inferred` for tables that have no description in OMD (all warehouse tables, plus copies such as `DepartmentTemp`): the term fits them by judgment, not documentation. |
| `term-relationships.csv` | Term to term relations (`subject, relation, object, evidence, source`) for the ontology step. `source=curated` rows carry domain-specific labels such as "placed by"; `source=fk` rows are generic `references` links derived from foreign keys. |

## Status values

- `Approved`: the *definition* is adapted from Microsoft's descriptions ingested in OMD. Individual tables mapped to the term can still be inferred; check `basis` in the mapping file.
- `Draft`: the definition is inferred from table and column names. This is every warehouse-only term (the Analytics domain), because the warehouse has no descriptions in OMD. Review these first.

## Importing into OMD

1. In OMD, create an **empty** glossary named exactly `AdventureWorks Business Glossary`. The import only works into an existing glossary.
2. Open the glossary, then use the import option on the glossary page, upload `adventureworks-glossary.csv` (pass 1), review the preview and confirm.
3. Import `adventureworks-glossary-relations.csv` (pass 2) the same way. It updates the existing terms with their related terms.
4. Optional pre-check without importing anything: `.venv/Scripts/python.exe -m tools.glossary.build dry-run` (pass 1) once the empty glossary exists; after pass 1 is imported, `dry-run --file adventureworks-glossary-relations.csv` checks pass 2. Reads `OMD_HOST` and `OMD_TOKEN` from `.env`.

## How it is built

Curated terms live in `tools/glossary/data/terms/*.json` (one file per domain), with curated relations in
`tools/glossary/data/relationships.json` and excluded tables in `tools/glossary/data/exclusions.json`.
Edit those, then regenerate from the repo root:

```
.venv/Scripts/python.exe -m tools.glossary.build snapshot   # refresh the OMD metadata snapshot (read-only)
.venv/Scripts/python.exe -m tools.glossary.build check      # validate; lists unmapped tables and bad references
.venv/Scripts/python.exe -m tools.glossary.build build      # write the four CSVs (only if the check passes)
```

`check` fails if a mapped table or column is not in the snapshot, a related term does not exist, a name contains a dot,
a warehouse-only term is marked `Approved`, or an in-scope table is neither mapped nor excluded.

## Notes

- Excluded tables: `DatabaseLog` and `ErrorLog` (audit logs), `AWBuildVersion` and `AdventureWorksDWBuildVersion` (build metadata), `sysdiagrams` (diagram storage).
- `AdventureWorks2019.dbo.Person` and `HumanResources.DepartmentTemp` are exact column copies of `Person.Person` and `Department`; they map to the same terms.
- `Dimension` and `Fact` are abstract concepts with no table of their own.
- `master` and `WideWorldImporters`, also ingested in OMD, are out of scope.
