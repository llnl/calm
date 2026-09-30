# Slab generation architecture

This page documents the current slab-generation path in CALM.

## Summary

CALM’s slab construction is designed to be:

- **Deterministic**: the same inputs produce the same slab geometry.
- **Traceable**: transformation metadata is stored alongside the generated slab.
- **Modernized**: legacy slab-generation pathways have been removed; the public API routes through a single implementation.

## Core components

### Public entry points

- [`calm.slab.Slab`](../reference/public_api.md): high-level slab object used throughout workflows.
- [`calm.slab.SlabSpec`](../reference/public_api.md): schema for describing a slab to be built.

### Oriented-slab metadata

When CALM generates a slab, it stores a JSON-serializable “transforms” payload under:

- `atoms.info["calm_oriented_slab_transforms_json"]`

This payload is intended to preserve enough information to reproduce or audit the construction steps (orientation, primitive reduction diagnostics, etc.).

See [Oriented slab transforms](oriented_slab_transforms.md).

### Primitive surface-cell reduction

Surface primitive reduction is implemented in:

- [`calm.slab.surface_primitive_cell`](../primitive_surface_cells.md)

The primary API is:

- `surface_primitive_slab(slab_supercell, **kwargs) -> (slab_prim, info)`

This reduces the in-plane periodicity of an oriented slab while preserving the surface normal.

## Current call chain

At a high level:

1. A `SlabSpec` describes orientation, thickness, vacuum, and whether primitive reduction should be attempted.
2. `Slab(...)` constructs an oriented slab.
3. If primitive reduction is enabled, `Slab` calls `surface_primitive_slab` to reduce the slab in-plane.
4. The transforms/diagnostics payload is stored in `atoms.info` for reproducibility.

Historically CALM included a “legacy” primitive-slab pathway behind a deprecated wrapper. That legacy code path has been removed; primitive reduction now routes through the modern surface-primitive implementation.
