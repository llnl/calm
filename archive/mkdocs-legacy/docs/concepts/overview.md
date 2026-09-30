# Concepts overview

CALM is organized around a few core domain concepts:

- **Bulk**: a 3D periodic crystal structure.
- **Material**: the chemistry + symmetry identity of a bulk; multiple bulks can map to the same material UID.
- **Slab**: a surface cut of a bulk for a given Miller index and slab specification.
- **Prototype**: a candidate commensurate in-plane match between two slabs (an interface *before* choosing strain partition/registry).
- **Strain state**: a choice of how much each slab is strained to match the interface lattice.
- **Interface**: an actual atomistic interface geometry (with registry/translation choices and z padding).

Two usage patterns are common:

1. **Workspace-backed workflows** (`calm.project.open_workspace`, `Workspace`): reproducible experiments with a SQLite database and stable UIDs.
2. **One-off workflows** (`calm.workflow` helpers): quick runs without persistent storage.

The public API is intentionally split into:

- **Computational kernels** (internal): pure-ish functions; minimal I/O; easy to test.
- **Public UX wrappers**: input validation, sensible defaults, stable signatures, richer objects.
