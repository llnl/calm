# Workspace Layout

A CALM workspace is a project directory containing the SQLite database and a
directory for generated files. This page describes the current, supported
layout and where to find authoritative details.

## Default layout

The default workspace layout is:

```text
<workspace-root>/
  calm.sqlite
  out/
```

`calm.sqlite` contains the persisted project state. `out/` stores generated
files such as plots, structure files, and tabular exports. The workspace root
is chosen by the user when opening or creating a workspace (see the public API
for details).

## What calm.sqlite stores

The SQLite database stores queryable project state: persisted records, UIDs,
provenance edges, run state, artifact registrations, datasets, campaigns, and
workspace configuration. The authoritative schema is implemented in
`calm/project/infrastructure/db/tables.py` and summarized in
[`docs/reference/workspace_database_schema.md`](../reference/workspace_database_schema.md).

For typical user workflows, prefer the public workspace API rather than direct
SQL access.

## What out/ stores

The `out/` directory contains human-readable artifacts produced by runs and
follow-up analyses. Examples include logs, plots, structure files (CIF/POSCAR),
tabular exports (CSV/JSON), and other files intended for inspection or export.

The database records artifact metadata and file paths; use the workspace API to
find associated artifacts rather than relying on ad-hoc directory conventions.

## Records versus files

Use this mental model:

| Location      | Role                                                                           |
| ------------- | ------------------------------------------------------------------------------ |
| `calm.sqlite` | Queryable project state: records, identifiers, provenance, runs, artifacts      |
| `out/`        | Generated files for humans, scripts, and external tools                        |

The database and artifact tree work together: runs create database records
and may write files under `out/`; queries should use the database to discover
what was created and how it relates to other records.

## Multiple workspaces

Different projects or phases of work can use separate workspace directories.
Each workspace has its own `calm.sqlite` and `out/` directory. Choose an
organization strategy (one workspace per project, per phase, or nested
hierarchies) that suits your team and reproducibility needs.

## What not to rely on

Avoid building workflows that depend on undocumented internal file paths,
historical layout conventions, or private modules. In particular, public
concept docs must not describe legacy layouts such as `.calm/calm.sqlite` as
current defaults unless the code and schema explicitly create them.

When in doubt use these authoritative references:

- Workspace API and usage: `docs/reference/workspace.md`
- Workspace persistence schema: `docs/reference/workspace_database_schema.md`
- Public API: `public_api.md` and `../reference/public_api.md`
