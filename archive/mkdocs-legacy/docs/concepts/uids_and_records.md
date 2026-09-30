# UIDs and Records

CALM uses stable identifiers to connect workspace records, generated artifacts,
and provenance relationships. This page gives a concise conceptual overview and
points to authoritative references for implementation details.

## Common identifier fields

Two identifier forms commonly appear in persisted records:

- `uid_full` — the full stable identifier used for durable references and
  internal provenance.
- `id_short` — a compact human-facing identifier used for display, tables, and
  interactive lookup.

Which identifier to use:

- Prefer `id_short` for interactive workflows, display, and examples.
- Preserve `uid_full` when storing durable references or when precision is
  required for reconstruction.

## Why CALM uses stable identifiers

Stable identifiers enable:

- reproducible references across sessions and machines;
- provenance linking between runs, records, and generated files;
- convenient, compact tables and exports for users and downstream tools;
- deduplication and caching when inputs are identical.

Users should normally rely on the workspace API and returned record objects
rather than inventing identifiers or constructing them by hand.

## Workspace records (conceptual)

The authoritative workspace schema and table list are implemented in
`calm/project/infrastructure/db/tables.py` and summarized in
[`docs/reference/workspace_database_schema.md`](../reference/workspace_database_schema.md).

Representative record families stored in the workspace database include:

- `bulks` — persisted bulk structures and their metadata
- `calculators` — serialized calculator specifications
- `slabs` — generated slab records derived from bulks
- `runs` and `artifacts` — workflow runs and registered artifact files
- `prototypes` and `derived_interfaces` — prototype candidates and derived specs
- `followup_results` — lightweight followup analysis summaries
- `edges` — provenance graph edges between records
- `jobs` — persistent task-queue records
- `migration_logs` — migration/audit records
- `datasets`, `dataset_items`, `campaigns`, `campaign_runs` — dataset & campaign persistence
- `project_configuration` — workspace-level configuration

For exact column names, constraints, and migration behavior consult the
implementation or the workspace database schema reference.

## Provenance and artifacts

Provenance is represented as explicit fields and graph edges linking records
(`edges` table). Larger human-readable outputs (logs, plots, structure files,
and tables) are written under the workspace `out/` directory and referenced via
the `artifacts` table. Use the workspace API to discover records and their
associated artifacts rather than relying on ad-hoc file paths.

## Records versus public exports

Public exports, sidecars, or report formats may use field names and layouts
convenient for downstream analysis. These export schemas are not identical to
the internal workspace SQLite schema. When documenting current persistence and
identifiers prefer the authoritative references listed below.

## Where to find authoritative details

- Workspace schema and tables: `calm/project/infrastructure/db/tables.py`
- Workspace schema summary: `docs/reference/workspace_database_schema.md`
- Public API and supported imports: `public_api.md` and
  `../reference/public_api.md`
- UID/hash internals and hashing spec: `docs/development/uid_hashing_specification.md`

If you need developer-level details about canonical JSON hashing, UID
construction, or canonicalization rules, consult the UID hashing specification
in the development docs rather than relying on conceptual summaries here.
