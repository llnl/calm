# Package layout

This page describes the intended package layout and the dependency boundaries between layers.

## Top-level packages

- **`calm`**: curated public API exports.
- **`calm.calculators`**: calculator registry + adapter utilities.
- **`calm.interface`**: interface matching, enumeration, scoring, and result objects.
- **`calm.project`**: workspace API + persistence (SQLite) + run/artifact management.
- **`calm.workflow`**: orchestration helpers that compose workspace + computational kernels.

## Layering rules (informal)

- **Core** modules must not import from `calm.project` or `calm.workflow`.
- **Workspace/persistence** (`calm.project`) may import from `calm.interface` and core modules.
- **Workflow** may import from `calm.project` and core modules.
- Public API modules should remain thin facades.

## Common subpackages

- `calm.interface.ops` — interface-layer orchestration helpers (below the workspace/workflow layer).
- `calm.project.application` — application services that wire persistence + domain logic.
- `calm.project.infrastructure` — database tables, repositories, and file stores.
- `calm.project.runner` — the run queue and execution loop.

## Why the workspace layer lives in `calm.project`

Historically, CALM used a "project" terminology for persistence-backed workflows. In the current architecture the user-facing abstraction is a **workspace** (`Workspace`), but the implementation remains under `calm.project` to avoid churn in internal module paths.
