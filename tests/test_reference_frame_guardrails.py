import numpy as np
import pytest
from ase.build import bulk as ase_bulk
from ase.build import make_supercell

from calm.bulk.bulk import Bulk
from calm.exceptions import ReferenceFrameError, ReferenceFrameFallbackWarning
import calm.interface.energy.reference as ie
from calm.interface.config import EnergyConfig
from calm.slab.oriented.transforms import ORIENTED_SLAB_TRANSFORMS_INFO_KEY
from calm.slab.slab import Slab
from calm.slab.slab import SlabSpec


def _mk_slab(element: str, a: float, hkl: tuple[int, int, int], n_layers: int):
    bulk_atoms = ase_bulk(element, a=a, cubic=True)
    bulk = Bulk(bulk_atoms)
    spec = SlabSpec(miller=hkl, n_layers=n_layers, vacuum=8.0, pbc=(True, True, True))
    slab = Slab(bulk, spec)

    # 2x2 in-plane supercell
    N = np.eye(3, dtype=int)
    N[0, 0] = 2
    N[1, 1] = 2
    slab_super = make_supercell(slab.atoms, N.T)
    return slab, slab_super


def _assert_rotation(Q: np.ndarray, tol: float = 1e-8) -> None:
    assert Q.shape == (3, 3)
    assert np.isfinite(Q).all()
    I = np.eye(3)
    assert np.max(np.abs(Q.T @ Q - I)) < 1e-7  # slightly looser than tol scaling
    det = float(np.linalg.det(Q))
    assert abs(det - 1.0) < 1e-6


def test_get_ortho_map_warns_on_forced_fallback(monkeypatch):
    slab, slab_super = _mk_slab("Al", 4.05, (1, 1, 1), n_layers=3)

    # Force primitive-basis method to fail deterministically
    monkeypatch.setattr(ie, "get_prim_in_slab", lambda *args, **kwargs: None)

    with pytest.warns(ReferenceFrameFallbackWarning):
        Q = ie.get_ortho_map(slab, slab_super, strict=False, warn=True, check=True, tol=1e-8)

    _assert_rotation(np.asarray(Q, dtype=float))


def test_get_ortho_map_strict_raises_on_forced_fallback(monkeypatch):
    slab, slab_super = _mk_slab("Al", 4.05, (1, 1, 1), n_layers=3)

    monkeypatch.setattr(ie, "get_prim_in_slab", lambda *args, **kwargs: None)

    with pytest.raises(ReferenceFrameError, match="forbids fallback|strict"):
        ie.get_ortho_map(slab, slab_super, strict=True, warn=False, check=True, tol=1e-8)


def test_get_strained_bulk_respects_energy_config_strict_without_provenance(
    monkeypatch,
):
    slab, slab_super = _mk_slab("Al", 4.05, (1, 1, 1), n_layers=3)
    F = np.eye(3, dtype=float)
    slab.atoms.info.pop(ORIENTED_SLAB_TRANSFORMS_INFO_KEY, None)

    monkeypatch.setattr(ie, "get_prim_in_slab", lambda *args, **kwargs: None)

    cfg = EnergyConfig(strict_reference_frame=True)
    with pytest.raises(ReferenceFrameError):
        ie.get_strained_bulk(slab, slab_super, F, config=cfg)


def test_get_strained_bulk_prefers_exact_transform_provenance(monkeypatch):
    slab, slab_super = _mk_slab("Al", 4.05, (1, 1, 1), n_layers=3)

    def unexpected_fallback(*args, **kwargs):
        raise AssertionError("geometric reference-frame recovery was used")

    monkeypatch.setattr(ie, "get_ortho_map", unexpected_fallback)
    strained = ie.get_strained_bulk(
        slab,
        slab_super,
        np.eye(3),
        config=EnergyConfig(strict_reference_frame=True),
    )

    assert np.isfinite(np.asarray(strained.cell.array, dtype=float)).all()


@pytest.mark.parametrize("element,a", [("Al", 4.05), ("Cu", 3.61)])
@pytest.mark.parametrize("hkl", [(1, 1, 1), (1, 1, 0), (1, 0, 0)])
@pytest.mark.parametrize("n_layers", [3, 6])
def test_get_ortho_map_stress(element, a, hkl, n_layers):
    slab, slab_super = _mk_slab(element, a, hkl, n_layers=n_layers)

    # Stress path should not raise in non-strict mode; silence warnings for CI noise
    Q = ie.get_ortho_map(slab, slab_super, strict=False, warn=False, check=True, tol=1e-8)

    _assert_rotation(np.asarray(Q, dtype=float))
