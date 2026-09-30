# Workspace Database Schema

CALM workspaces persist structured project state in a SQLite database named
`calm.sqlite` at the workspace root by default.

The implementation source of truth for the current workspace schema is:

```text
calm/project/infrastructure/db/tables.py
```

This page is a documentation summary of that implementation. If this page and
the source code disagree, the source code is authoritative.

## Workspace persistence model

A default workspace has the form:

```text
<workspace-root>/
  calm.sqlite
  out/
```

The SQLite database stores structured records, IDs, provenance, queue state,
campaign state, and references to artifacts. Larger human-readable outputs such
as logs, plots, tables, structures, and other generated files are written under
`out/`.

The database is intended for queries and provenance. The `out/` directory is
intended for inspection, export, and external tools.

## Current tables

The current workspace database tables are defined in
`calm/project/infrastructure/db/tables.py`.

| Table                   | Purpose                                                                                                                                            |
| ----------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| `schema_version`        | Records applied schema versions and CALM version metadata for migrations.                                                                          |
| `bulks`                 | Stores bulk structure records added to the workspace, including stable IDs, labels, kind, optional calculator provenance, and serialized payloads. |
| `calculators`           | Stores serialized calculator specifications, including calculator family, model, device, and content-addressed identifiers.                        |
| `slabs`                 | Stores generated slab records derived from bulks, including Miller indices, tilt summaries, orthogonalization metadata, and serialized payloads.   |
| `runs`                  | Stores workflow run records, including run type, status, specification JSON, progress JSON, and error JSON.                                        |
| `artifacts`             | Registers files associated with runs, including artifact kind, URI, metadata, and run linkage.                                                     |
| `prototypes`            | Stores interface prototype candidates associated with prototype-search runs and parent slabs.                                                      |
| `derived_interfaces`    | Stores persisted interface specifications derived from prototypes. These records are spec-based and can be reconstructed on demand.                |
| `followup_results`      | Stores lightweight queryable summaries of follow-up analyses associated with runs and prototypes. Larger outputs should be artifacts.              |
| `edges`                 | Stores provenance graph edges between records, including edge kind and serialized payload metadata.                                                |
| `jobs`                  | Stores persistent task-queue records, including job type, status, priority, retry state, parent job, and optional run linkage.                     |
| `migration_logs`        | Stores durable audit records for migration operations and rollback-oriented workflows.                                                             |
| `datasets`              | Stores dataset definitions and metadata.                                                                                                           |
| `dataset_items`         | Stores dataset membership records and item-level metadata/artifact references.                                                                     |
| `campaigns`             | Stores campaign definitions and serialized campaign specifications.                                                                                |
| `project_configuration` | Stores workspace-level configuration such as default calculator and workflow defaults.                                                             |
| `campaign_runs`         | Stores campaign execution records, backend identifiers, status, and uniqueness metadata for resumable campaign execution.                          |

## Common record fields

Many workspace tables use a common identity pattern:

| Field          | Meaning                                                                                                 |
| -------------- | ------------------------------------------------------------------------------------------------------- |
| `uid_full`     | Stable full identifier for the record.                                                                  |
| `id_short`     | Short human-facing identifier used in interactive workflows and examples.                               |
| `payload_json` | Serialized record payload where the record stores flexible structured metadata.                         |
| `spec_json`    | Serialized specification for records that represent reproducible operations or reconstructable objects. |
| `created_at`   | Timestamp for record creation.                                                                          |
| `updated_at`   | Timestamp for the latest record update, where applicable.                                               |

Not every table has every field. Consult `tables.py` for the exact columns,
constraints, and foreign keys.

## Files and artifacts

CALM does not store all large generated outputs directly in the database.
Instead, run-associated files are written under `out/` and registered in the
`artifacts` table.

Typical artifact paths are organized under:

```text
<workspace-root>/out/runs/<run-id>/
  logs/
  plots/
  structures/
  tables/
  files/
```

The exact artifact path depends on the workspace operation and artifact helper
used.

## Workspace schema versus public sidecar/export schemas

This page describes the internal workspace SQLite schema.

CALM may also provide public export files, sidecars, datasets, or reports with
their own record names. Those export schemas are not identical to the workspace
SQLite schema.

When documenting current workspace persistence, use the table names listed on
this page and implemented in `calm/project/infrastructure/db/tables.py`.

## Historical naming note

Older engineering notes or historical documents may mention names such as
`materials`, `search_runs`, `strains`, `interfaces`, or `energies` as if they
were workspace database tables. Those names should not be treated as the current
workspace SQLite schema unless they are reintroduced in `tables.py`.

For current behavior, prefer:

* `bulks`, `slabs`, `runs`, `prototypes`, `derived_interfaces`,
  `followup_results`, and `artifacts` for workspace workflow records;
* `datasets`, `dataset_items`, `campaigns`, and `campaign_runs` for dataset and
  campaign persistence;
* `jobs` for persistent queue state;
* `migration_logs` for migration audit records.
