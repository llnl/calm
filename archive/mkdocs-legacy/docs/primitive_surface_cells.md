# Primitive surface cells in CALM

This note documents the **modern** primitive surface-cell pipeline used by CALM.

The goal of primitive surface-cell reduction is to take a slab *supercell* (often
constructed from a bulk conventional cell + Miller index) and compute a
**motif-compatible primitive in-plane cell**. This improves:

- deterministic slab identifiers / de-duplication,
- symmetry canonicalization,
- and downstream interface enumeration cost.

Legacy implementations and legacy public entrypoints have been intentionally
removed. If you see references to `calm.legacy.*` or
`calm.symmetry.reduction.get_prim_slab`, treat them as historical artifacts.

---

## Recommended entrypoints

### 1) Oriented-slab workflow (preferred)

If you are working with CALM's modern oriented-slab stack, use the oriented-slab
helpers in `calm.slab.surface_primitive_cell`:

- `calm.slab.oriented_slab_surface_primitive_cell(...)`
- `calm.slab.surface_primitive_from_slabs(...)`

These helpers return the **surface primitive cell transform** (`N`, `Ninv`) and a
warning string (empty/falsey if none). They are designed to be
**DeprecationWarning-clean** and to preserve provenance via oriented-slab
transforms.

### 2) Slab/Atoms primitive reduction (low-level)

If you need to directly reduce a slab supercell to a primitive in-plane cell,
use:

- `calm.slab.surface_primitive_slab(slab_supercell, *, strict=True, warn_on_fallback=True) -> (slab_prim, info)`

This returns:

- `slab_prim`: an ASE `Atoms` representing the reduced slab (or the original slab
  on fallback when `strict=False`), and
- `info`: a diagnostics dictionary describing the reduction.

---

## Backend architecture

CALM enforces **import hygiene** so that the heavy primitive-slab backend is not
pulled in by default.

- Importing `calm.slab` / `calm.slab.surface_primitive_cell` should stay
  lightweight.
- The backend implementation lives in `calm.symmetry.surface_primitive` and is
  imported lazily only when primitive reduction is invoked.

This is intentional: the backend pulls in heavier numerical dependencies (e.g.
SciPy for KDTree-based nearest-neighbor searches).

---

## Semantics: strict vs fallback

Primitive reduction can fail for legitimately hard numerical/symmetry reasons
(e.g., ambiguous motifs under tolerances).

The core policy knobs are:

- `strict=True`: raise `PrimitiveSlabError` on failure.
- `strict=False`: fall back to the original slab cell.

Warnings are controlled by:

- `warn_on_fallback=True`: emit a `PrimitiveSlabFallbackWarning` when a fallback
  occurs.
- `warn_on_fallback=False`: stay quiet.

The higher-level `Slab` construction path typically wires `warn_on_fallback` to
user-facing verbosity controls (so `verbose=False` yields quiet construction).

---

## Practical guidance

- Prefer the oriented-slab entrypoints unless you are explicitly operating on raw
  `ase.Atoms` objects.
- Use `strict=False` for exploratory workflows where "best effort" is acceptable.
- Use `strict=True` for debugging / validation when you want failures to be
  loud.

---

## Developer references

- Roadmap and migration notes: `ROADMAP_PRIMITIVE_SURFACE_CELLS.md`
- Backend implementation: `calm.symmetry.surface_primitive`
- Slab-facing wrapper: `calm.slab.surface_primitive_cell`


## Performance notes

Most of the primitive surface-cell pipeline is NumPy linear algebra and scales well for the
problem sizes we encounter in slab/interface enumeration.

The only materially heavier step is the **integer lattice saturation** routine
(``calm.symmetry.surface_primitive.primitive_generators_from_C_snf``), which uses SymPy's
Smith normal form decomposition. This is required for correctness in edge cases.

To keep enumeration workloads fast, the SNF-based generator step is **LRU-cached by value**.
If you are iterating over many candidates that reuse the same ``C`` matrices (common when
only origins change), the cache avoids repeated SymPy work.

When profiling, prefer:

- ``python -m cProfile -o profile.pstats ...`` and ``snakeviz profile.pstats``
- focusing on repeated calls inside enumeration loops (rather than one-off slab construction)

If SymPy ever becomes the dominant cost in a real workload, the next step would be to
replace the general SNF call with a bespoke, small-matrix integer routine (3×2 rank-2), while
keeping the same interface and test coverage.

