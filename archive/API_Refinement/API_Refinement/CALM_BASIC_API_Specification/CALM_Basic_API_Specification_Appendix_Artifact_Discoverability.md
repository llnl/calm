# Appendix — Project Artifacts and Discoverability

## Purpose

This appendix defines the Basic API's conventions for exported artifacts,
their default discovery location, and related user-facing helpers.  It is
intended to make the exported-output experience (tables, plots, reports,
structure files) explicit and discoverable without exposing storage
implementation details.

## Default artifact root

When the user does not supply an explicit destination to an `export(...)`
operation, the Basic API writes exported artifacts to a project-local
artifact directory named `CALM_results/` inside the Project root.  This
default is a user-facing convenience to improve discoverability and to keep
project deliverables co-located with the project state.

Example layout (conceptual):

```
<project-root>/CALM_results/
    tables/
    plots/
    reports/
    structures/
    datasets/
```

Implementations may choose specific on-disk file names and formats; the
Basic API requires only that the artifact root is discoverable programmatically
via the Project.

## Programmatic discovery

The Project shall expose helpers that allow users to discover exported
artifacts without inspecting file-system internals.  Minimum helpers include:

- `project.artifacts.root()` → path to the artifact root (string or Path)
- `project.artifacts.list(pattern=None)` → list of artifact paths matching pattern
- `project.artifacts.find_by_kind(kind)` → list artifacts of kind: `tables`,
  `plots`, `reports`, `structures`, `datasets`

These helpers are intentionally lightweight and discoverable from the public
Project object so users never need to inspect database tables or implementation
paths directly.

## Export semantics

Public collection `export(...)` methods accept an explicit destination path
and optional format arguments.  When a destination is omitted the Basic API
uses the artifact root and a stable naming convention to write the artifact.

All exported artifacts should include provenance metadata when the output
format supports it.  At a minimum exported tables and archives should embed or
adjacent sidecar the following information:

- originating project id/path
- originating object ids (where applicable)
- generation timestamp
- export format version

## Reporting vs persisted scientific objects

Exported artifacts are not themselves persisted scientific objects unless the
Basic API explicitly models them as such (for example, `Dataset` is a
persisted scientific object, whereas `ParetoPlot.png` is an exported artifact).

Persisted scientific objects remain discoverable through the Project's
collections.  Exported artifacts are discoverable through the Project's
artifact helpers and `CALM_results/` default location.

## User control

Users control exported outputs via the standard `export(...)` arguments:

- explicit `destination`
- optional `format` (e.g. CSV, JSON, PDF, PNG, ZIP)
- optional `view`/`scope` arguments where collections support multiple views
- optional `metadata` to include as export-sidecar

When explicit `destination` is provided, the Basic API must not write to the
default artifact root.

## Compatibility

The default artifact root and the programmatic helpers are part of the Basic
API contract and are expected to remain stable across releases.  Implementers
should ensure that exported artifacts written by older versions remain
discoverable by these helpers when the project is reopened.
