"""calm.keys.hnf

Canonical Hermite normal-form (HNF) utilities for 2D integer lattice maps.

This module is intentionally small and dependency-light. It provides:

* ``canonical_hnf_under_pg_with_witness``: deterministic one-sided orbit
  canonicalization with exact point-group and right-unimodular witnesses.

The key design requirement is **determinism** under **left action** by
point-group operations (including reflections).

Important nuance:
The returned key is designed for **grouping one-sided surface cells under
symmetry in a fixed, already-canonical primitive surface gauge**. It is not the
authoritative coupled A/B prototype identity; exact coupled deduplication is
owned by the paired-lattice canonicalization path.

The previous implementation attempted to compute HNF via ad hoc row/column
operations and could emit non-canonical representatives with negative diagonals.
That manifested as sign-flips in orbit keys under reflections. The implementation
below follows the standard 2×2 right-HNF construction using a Bezout step to
zero the lower-left entry, followed by canonical reductions.

Performance notes
-----------------
Surface-orbit enumeration calls the witness path for every admitted reduced
supercell. For tight loops, callers may pre-normalize and freeze the point-group
operation list once with :func:`normalize_pg_ops_frozen`.

This is an internal acceleration aid and does not change external behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from calm.symmetry.surface_group import validate_surface_symmetry_group_2d

# 2×2 canonical normal forms live in calm.math2d.
from calm.math2d.normal_forms import hnf2_col_with_transform

_IDENTITY_2D = np.eye(2, dtype=int)


class _NormalizedPGOps(tuple):
    """Internal marker wrapper for pre-normalized 2D point-group ops.

    Instances are immutable tuples of 2×2 integer matrices with det=±1.

    Rationale
    ---------
    Normalizing/validating point-group ops is cheap per call, but in supercell
    enumeration the same op list is reused thousands of times. Wrapping a
    normalized op list once avoids repeated list construction and det checks.

    This is intentionally *private* to avoid becoming part of the public API.
    """

    __slots__ = ()


def _integer_matrix_2x2(name: str, value: object) -> np.ndarray:
    """Return an exact 2x2 integer matrix without truncating floats."""
    matrix = np.asarray(value)
    if matrix.shape != (2, 2):
        raise ValueError(f"{name} must have shape (2, 2).")
    if matrix.dtype.kind not in {"i", "u"}:
        raise TypeError(f"{name} must contain exact integer values.")
    return np.asarray(matrix, dtype=int)


def _normalize_pg_ops(PG_ops: Sequence[np.ndarray]) -> list[np.ndarray]:
    """Validate and deterministically order a 2D point group.

    Operations are exact elements of ``GL(2, Z)``. The empty sequence retains
    the historical meaning of the explicit identity-only group. Any non-empty
    sequence must explicitly contain identity and satisfy closure and inverse
    membership; canonical orbit code never treats an arbitrary finite transform
    list as a mathematical point group.
    """

    candidates: Sequence[np.ndarray]
    if len(PG_ops) == 0:
        candidates = (_IDENTITY_2D,)
    else:
        candidates = PG_ops
    return list(validate_surface_symmetry_group_2d(candidates))


def normalize_pg_ops_frozen(PG_ops: Sequence[np.ndarray]) -> Sequence[np.ndarray]:
    """Return a frozen (immutable) normalized op sequence.

    This is an internal performance helper: it normalizes once and returns an
    immutable tuple-like wrapper that the witness canonicalizer recognizes.

    Notes
    -----
    - The returned sequence should be treated as read-only.
    - The wrapper is intentionally not exported from ``calm.keys``.
    """

    return _NormalizedPGOps(tuple(_normalize_pg_ops(PG_ops)))


@dataclass(frozen=True)
class HNFOrbitCanonicalization2D:
    """Exact witness for one-sided HNF orbit canonicalization."""

    key: tuple[int, int, int, int]
    canonical_hnf: np.ndarray
    point_operation: np.ndarray
    right_transform: np.ndarray


def canonical_hnf_under_pg_with_witness(
    matrix: np.ndarray,
    operations: Sequence[np.ndarray],
) -> HNFOrbitCanonicalization2D:
    """Canonicalize one integer map and retain the exact orbit witness.

    The returned matrices satisfy

    ``canonical_hnf = point_operation @ matrix @ right_transform``.

    ``point_operation`` belongs to the validated one-sided surface group and
    ``right_transform`` is unimodular. The flattened canonical HNF is returned
    directly as ``key``.
    """

    source = _integer_matrix_2x2("matrix", matrix)
    if isinstance(operations, _NormalizedPGOps):
        normalized = operations
    else:
        normalized = _normalize_pg_ops(operations)

    best_rank: tuple[object, ...] | None = None
    best: HNFOrbitCanonicalization2D | None = None
    source_exact = np.asarray(source, dtype=object)
    for operation in normalized:
        operation_exact = np.asarray(operation, dtype=object)
        orbit_member = operation_exact @ source_exact
        canonical_hnf, right_transform = hnf2_col_with_transform(orbit_member)
        key = (
            int(canonical_hnf[0, 0]),
            int(canonical_hnf[0, 1]),
            int(canonical_hnf[1, 0]),
            int(canonical_hnf[1, 1]),
        )
        operation_key = tuple(int(value) for value in operation.ravel())
        transform_key = tuple(int(value) for value in right_transform.ravel())
        rank = (key, operation_key, transform_key)
        if best_rank is not None and rank >= best_rank:
            continue
        reconstructed = orbit_member @ np.asarray(right_transform, dtype=object)
        if not np.array_equal(reconstructed, canonical_hnf):
            raise RuntimeError(
                "canonical_hnf_under_pg_with_witness: exact reconstruction failed"
            )
        best_rank = rank
        best = HNFOrbitCanonicalization2D(
            key=key,
            canonical_hnf=np.asarray(canonical_hnf, dtype=int),
            point_operation=np.asarray(operation, dtype=int),
            right_transform=np.asarray(right_transform, dtype=int),
        )

    if best is None:
        raise RuntimeError("canonical_hnf_under_pg_with_witness: empty validated orbit")
    return best
