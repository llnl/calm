# Development roadmap

This document tracks engineering milestones and refactors that are useful for maintaining clean boundaries between layers.

## Milestone R1: Stabilize the workspace API

- Keep the `Workspace` API small and explicit.
- Ensure docs/examples only depend on the public API inventory.
- Maintain deterministic behavior across runs (tie-breaking, ordering, serialization).

## Milestone R2: Reduce coupling between algorithms and persistence

- Keep algorithmic tests runnable without a database.
- Prefer pure functions + immutable result objects in `calm.interface`.
- Add thin adapters when persistence is required (store reads/writes, artifact plumbing).

## Milestone R3: Persistence abstraction for the workspace layer

- Isolate SQLAlchemy usage to `calm.project.infrastructure`.
- Keep repositories/unit-of-work small and testable.
- Make it easy to swap storage backends in the future (filesystem-only, in-memory, alternative DB).
