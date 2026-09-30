# Refinement pruning

This page documents the canonical refinement-pruning algorithm used to
detect and remove strict simultaneous refinements of candidate supercell
pairs. The algorithm is closely related to the canonicalization/deduplication
primitives in `deduplication-equivalence-and-canonicalization.md` but is
presented here as its own canonical spec because it describes a concrete
deterministic pruning workflow used by downstream matching code.

## Scope

This page specifies:

- the deterministic sorting and selection order used during pruning
- Smith Normal Form (SNF) signatures used to identify strict simultaneous refinements
- orbit-aware SNF comparison to handle point group symmetries
- the greedy pruning loop and correctness properties

## Definitions and contracts

See `deduplication-equivalence-and-canonicalization.md` for canonical HNF
orbit keys and prototype-signature definitions. This page assumes those
primitives and specifies how they are used operationally by the pruning
workflow.

## Algorithm overview

1. deterministically sort candidates by (size, score, d_cell) where size = max(det_A, det_B)
2. for each candidate in sorted order, test whether it is a strict simultaneous refinement of any previously-kept candidate
3. if it is a strict simultaneous refinement, drop it; otherwise keep it

### Deterministic sorting

Sort by lexicographic tuple: (size ascending, match_score ascending, d_cell ascending)
to ensure deterministic pruning outcomes across different runs.

### SNF-based simultaneous refinement test

Given candidate transforms N_tot_big and N_tot_small, compute SNF signatures
for the integer refinement matrix K where N_tot_big = N_tot_small · K. If K
is strictly integer with determinant > 1 and the SNF signature indicates a
proper lattice refinement (no nontrivial unit divisors), then the bigger
candidate is a strict refinement.

### Orbit-aware comparisons

Because HNF representatives may lie in the same point-group orbit, compute
SNF signatures across the canonical orbit representatives and compare the
minimal signature lexicographically to determine equivalence/refinement.

## Implementation mapping

- calm.interface.prototypes.hnf_refinement_signature
- calm.interface.pruning.prune_refinements_keep_smallest_snf
- calm.keys.hnf.canonical_hnf_key_under_pg

## Correctness and invariants

The pruning loop is designed to be deterministic and stable with respect to
the canonical HNF key ordering and the sorting tuple above. It relies on
canonical orbit representatives for robust comparisons under symmetry.

## Appendix: Practical notes

Small practical guidelines for implementers:

- use exact integer arithmetic whenever possible for SNF tests
- cache orbit representatives and SNF signatures when pruning many candidates
- provide verbose diagnostics when pruning rate is unexpectedly high
