"""benchmarks.benchmark_pairs

Defines a small set of **2D lattice-pair benchmarks**.

Conventions
-----------
- Each 2D basis is a (2,2) numpy array with **basis vectors stored as columns**.
  This matches the convention used internally by PyIntExp/SlabGen.
- Units are arbitrary (typically Angstrom).

These benchmarks are deliberately geometry-only: they avoid any dependence on
real slab motifs/terminations while still exercising the core lattice matching
logic (enumeration, canonicalization, mismatch/strain metrics, and size tradeoffs).

The current default set includes three cases:

1) rect_small_mismatch
   A rectangular/orthorhombic-like case with small mismatch.
2) hex_near_degenerate
   A near-hexagonal metric case (≈60°), which stresses reduction tie regions.
3) oblique_tradeoff
   A generic oblique case with a visible mismatch–size tradeoff.

"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np


@dataclass(frozen=True)
class LatticePair2D:
    """A named benchmark consisting of two 2D lattices."""

    name: str
    A: np.ndarray  # (2,2) basis, columns are lattice vectors
    B: np.ndarray  # (2,2) basis, columns are lattice vectors
    comment: str = ""


def _col_basis(v1, v2) -> np.ndarray:
    """Create a 2x2 column basis from two 2D vectors."""

    M = np.array([[v1[0], v2[0]], [v1[1], v2[1]]], dtype=float)
    if M.shape != (2, 2):
        raise ValueError("Expected two 2D vectors")
    return M


def default_benchmark_pairs() -> List[LatticePair2D]:
    """Return the default 3-pair benchmark set."""

    # 1) Rectangular lattices with small mismatch.
    A1 = _col_basis((3.00, 0.00), (0.00, 4.00))
    B1 = _col_basis((3.12, 0.00), (0.00, 3.92))

    # 2) Near-hexagonal metrics (≈ 60°), slightly perturbed.
    #    This is a common reduction-boundary stress case.
    aA = 2.50
    aB = 2.53
    angA = np.deg2rad(60.00)
    angB = np.deg2rad(60.20)
    A2 = _col_basis((aA, 0.0), (aA * np.cos(angA), aA * np.sin(angA)))
    B2 = _col_basis((aB, 0.0), (aB * np.cos(angB), aB * np.sin(angB)))

    # 3) Generic oblique lattices chosen to produce a visible strain–size tradeoff.
    A3 = _col_basis((3.10, 0.40), (0.20, 2.30))
    B3 = _col_basis((2.90, 0.25), (0.60, 2.80))

    return [
        LatticePair2D(
            name="rect_small_mismatch",
            A=A1,
            B=B1,
            comment="Rectangular lattices; good for count-vs-area scaling.",
        ),
        LatticePair2D(
            name="hex_near_degenerate",
            A=A2,
            B=B2,
            comment="Near-hexagonal metrics; stresses 2D reduction/canonicalization tie regions.",
        ),
        LatticePair2D(
            name="oblique_tradeoff",
            A=A3,
            B=B3,
            comment="Generic oblique lattices; yields a mismatch–size Pareto tradeoff.",
        ),
    ]


# -----------------------------------------------------------------------------
# Registry helpers
# -----------------------------------------------------------------------------
#
# Several benchmarking scripts treat the benchmark pairs as a named registry.
# Earlier versions used a module-level BENCHMARK_PAIRS mapping; newer versions
# expose `default_benchmark_pairs()`.
#
# To keep scripts stable (including paper-figure scripts) we provide both.


BENCHMARK_PAIRS: dict[str, LatticePair2D] = {p.name: p for p in default_benchmark_pairs()}


def get_benchmark_pair(name: str) -> LatticePair2D:
    """Return a benchmark pair by name.

    Parameters
    ----------
    name
        Name key, e.g. "oblique_tradeoff".

    Raises
    ------
    KeyError
        If the pair name is unknown.
    """
    try:
        return BENCHMARK_PAIRS[name]
    except KeyError as exc:
        known = ", ".join(sorted(BENCHMARK_PAIRS))
        raise KeyError(f"Unknown benchmark pair '{name}'. Known: {known}") from exc


def basis_to_3d_vectors(S2: np.ndarray):
    """Convert a 2x2 column-basis into two 3D vectors with z=0."""

    S2 = np.asarray(S2, dtype=float)
    if S2.shape != (2, 2):
        raise ValueError("S2 must be (2,2)")

    v1 = np.array([S2[0, 0], S2[1, 0], 0.0], dtype=float)
    v2 = np.array([S2[0, 1], S2[1, 1], 0.0], dtype=float)
    return [v1, v2]


def basis_area(S2: np.ndarray) -> float:
    """Return the absolute 2D cell area |det(S2)| for a 2x2 column basis."""

    S2 = np.asarray(S2, dtype=float)
    if S2.shape != (2, 2):
        raise ValueError("S2 must be (2,2)")
    return float(abs(np.linalg.det(S2)))
