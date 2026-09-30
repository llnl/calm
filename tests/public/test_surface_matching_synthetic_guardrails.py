"""Synthetic surface-matching guardrails for bounded HNF enumeration.

These tests use tiny slab-like doubles so they exercise the matching
mathematics without constructing real ASE slabs. Importing the current matching
pipeline still requires the optional symmetry backend modules to be importable
because ``calm.interface.types`` imports ``calm.symmetry.reduction`` through the
package initializer. The tests therefore skip in lightweight environments where
those optional backends are unavailable.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pytest

pytest.importorskip("ase")
pytest.importorskip("spglib")

from calm.interface.config import PrototypeSearchConfig
from calm.interface.matching.search import enumerate_primitive_match_classes


@dataclass(frozen=True)
class _Cell:
    array: np.ndarray


@dataclass(frozen=True)
class _Atoms:
    cell: _Cell


@dataclass(frozen=True)
class _SyntheticSlab:
    atoms: _Atoms
    n_atoms: int = 1


def _orthogonal_slab(a: float, b: float) -> _SyntheticSlab:
    """Return a minimal slab-like object with an orthogonal in-plane cell."""
    cell = np.asarray(
        [
            [float(a), 0.0, 0.0],
            [0.0, float(b), 0.0],
            [0.0, 0.0, 10.0],
        ],
        dtype=float,
    )
    return _SyntheticSlab(atoms=_Atoms(cell=_Cell(array=cell)))


def test_bounded_matching_requires_sufficient_hnf_index_for_exact_synthetic_match() -> None:
    """A commensurate area-2 pair is unavailable when k_max excludes k=2."""
    slab_a = _orthogonal_slab(1.0, 1.0)
    slab_b = _orthogonal_slab(2.0, 1.0)

    matches = enumerate_primitive_match_classes(
        slab_a,
        slab_b,
        PrototypeSearchConfig(
            k_max=1,
            eps_principal_max=1.0e-12,
            cond_max=1.0e6,
            w_match=1.0,
            N_at_max=100,
            surface_symmetry_mode="identity_only",
        ),
    )

    assert matches == []


def test_bounded_matching_finds_exact_synthetic_supercell_when_index_is_available() -> None:
    """The same pair becomes a zero-strain match once kA=2 is admissible."""
    slab_a = _orthogonal_slab(1.0, 1.0)
    slab_b = _orthogonal_slab(2.0, 1.0)

    matches = enumerate_primitive_match_classes(
        slab_a,
        slab_b,
        PrototypeSearchConfig(
            k_max=2,
            eps_principal_max=1.0e-12,
            cond_max=1.0e6,
            w_match=1.0,
            N_at_max=100,
            surface_symmetry_mode="identity_only",
        ),
    )

    exact = [
        match_class
        for match_class in matches
        if (2, 1) in match_class.source_index_pairs
        and match_class.representative.ai_strain.max_abs_principal_strain
        < 1.0e-12
    ]
    assert exact
    representative = exact[0].representative
    assert representative.ai_strain.d_cell == pytest.approx(0.0, abs=1.0e-12)
    # The affine-invariant cell distance is exactly zero for this synthetic
    # commensurate pair.  The aggregate match score can still include small
    # secondary regularization terms, so this guardrail checks the mathematical
    # zero-strain invariant directly rather than over-constraining the scorer.
    assert representative.match_score >= 0.0
