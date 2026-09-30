# Architecture

The CALM codebase is organized into layers to keep the computational kernels usable without the database-backed workflow stack.

## Goals

1. Keep computational kernels (geometry / lattice / enumeration / energy evaluation logic) usable without persistence.
2. Keep persistence + orchestration concerns isolated behind a workspace API.
3. Maintain a small, explicit public API surface.

## Layering

| Layer | Module root | Purpose |
| --- | --- | --- |
| **Core** | `calm.*` (excluding `calm.interface`, `calm.project`, `calm.workflow`) | Pure computation + data structures. No persistence, no runner, minimal imports. |
| **Interface** | `calm.interface` | Interface enumeration, matching, scoring, and result objects. Designed to be usable in-memory. |
| **Workspace (persistence)** | `calm.project` | SQLite-backed persistence, runs, artifacts, and the `Workspace` API (opened via `open_workspace(...)`). |
| **Workflow** | `calm.workflow` | Higher-level orchestration helpers that compose workspace + core. |
| **Public API** | `calm.api` (+ curated exports in `calm/__init__.py`) | Small, stable surface intended for downstream users and docs. |

## Dependency rules

1. **Core** must not depend on **Workspace**, **Workflow**, or **Public API**.
2. **Workspace** may depend on **Interface** and **Core**.
3. **Workflow** may depend on **Workspace** and **Core**.
4. **Public API** may depend on any layer, but should remain a thin facade.

These boundaries are enforced by tests in `tests/arch/`.

## Import guidance

- Prefer **public exports** where available.
- When you need workspace features, prefer:

```python
  from calm.project import Workspace, open_workspace
```

- Avoid importing directly from low-level infrastructure modules (for example, `calm.project.infrastructure.*`) unless you are working on the persistence implementation itself.
