"""Application-service contracts for conventional principal strain directions."""

from __future__ import annotations

from types import ModuleType, SimpleNamespace
import sys

import numpy as np

from calm.project.application.prototype_analysis import PrototypeAnalysisService
from oriented_slab_fixtures import current_construction_controls


class _Repository:
    def __init__(self, objects):
        self._objects = dict(objects)

    def get_by_uid_full(self, uid):
        return self._objects.get(uid)


class _Ids:
    @staticmethod
    def resolve_prototype(value):
        return value


class _UnitOfWork:
    def __init__(self, *, prototype, slabs, bulks):
        self.ids = _Ids()
        self.prototypes = _Repository({prototype.uid_full: prototype})
        self.slabs = _Repository(slabs)
        self.bulks = _Repository(bulks)
        self._entered = False

    def __enter__(self):
        self._entered = True
        return self

    def __exit__(self, exc_type, exc, traceback):
        self._entered = False
        return False


class _Atoms:
    def __init__(self, *, cell, formula="Cu", transforms=None):
        self._cell = SimpleNamespace(array=np.asarray(cell, dtype=float))
        self._formula = formula
        self.transforms_payload = transforms

    def get_cell(self):
        return self._cell

    def get_chemical_formula(self, **_kwargs):
        return self._formula


def _rotation_z(theta_deg: float) -> np.ndarray:
    theta = np.deg2rad(theta_deg)
    c = float(np.cos(theta))
    s = float(np.sin(theta))
    return np.array(
        [[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]],
        dtype=float,
    )


def _analysis(monkeypatch, *, strain_info):
    proto = SimpleNamespace(
        uid_full="proto:test",
        slab_a_uid_full="slab:a",
        slab_b_uid_full="slab:b",
    )
    slab_a_atoms = _Atoms(
        cell=np.eye(3),
        transforms={
            "version": 1,
            "hkl": [1, 0, 0],
            "U": _rotation_z(-45.0),
            "M_slab_to_conv_cart": _rotation_z(45.0),
            "M_conv_to_slab_cart": _rotation_z(-45.0),
            "construction_controls": current_construction_controls(),
        },
    )
    slab_b_atoms = _Atoms(
        cell=np.eye(3),
        transforms={
            "version": 1,
            "hkl": [1, 0, 0],
            "U": np.eye(3),
            "M_slab_to_conv_cart": np.eye(3),
            "M_conv_to_slab_cart": np.eye(3),
            "construction_controls": current_construction_controls(),
        },
    )
    slabs = {
        "slab:a": SimpleNamespace(
            bulk_uid_full="bulk:a",
            atoms=slab_a_atoms,
        ),
        "slab:b": SimpleNamespace(
            bulk_uid_full="bulk:b",
            atoms=slab_b_atoms,
        ),
    }
    bulks = {
        "bulk:a": SimpleNamespace(
            atoms_conventional=_Atoms(cell=np.eye(3), formula="Cu2"),
        ),
        "bulk:b": SimpleNamespace(
            atoms_conventional=_Atoms(cell=np.eye(3), formula="Ni"),
        ),
    }
    service = PrototypeAnalysisService(
        uow_factory=lambda: _UnitOfWork(
            prototype=proto,
            slabs=slabs,
            bulks=bulks,
        )
    )
    loaded_prototype = SimpleNamespace(
        slab_a=slabs["slab:a"],
        slab_b=slabs["slab:b"],
    )
    monkeypatch.setattr(
        "calm.project.application.prototype_analysis.load_interface_prototype",
        lambda _uow, _uid: loaded_prototype,
    )
    monkeypatch.setattr(
        PrototypeAnalysisService,
        "_strain_payload",
        staticmethod(lambda _context, **_kwargs: strain_info),
    )

    slab_module = ModuleType("calm.slab.slab")

    def get_payload(atoms, *, strict=False):
        payload = atoms.transforms_payload
        if payload is None and strict:
            raise KeyError("missing transforms")
        return payload

    slab_module.get_oriented_slab_transforms_payload = get_payload
    monkeypatch.setitem(sys.modules, "calm.slab.slab", slab_module)
    return service


def _side(*, status: str, directions):
    return {
        "principal_strains": [-0.01, 0.02],
        "principal_directions_cart": directions,
        "principal_direction_status": status,
        "principal_eigengap": 0.03 if status == "defined" else 0.0,
        "principal_eigengap_threshold": 2.0e-5,
        "principal_eigenspace_projector": (
            None if status == "defined" else np.eye(2).tolist()
        ),
    }


def test_service_uses_stored_slab_to_conventional_frame(monkeypatch) -> None:
    strain_info = {
        "alpha": 0.5,
        "alpha_convention": (
            "alpha=0 leaves A unstrained; alpha=1 leaves B unstrained"
        ),
        "slab_A": _side(status="defined", directions=np.eye(2).tolist()),
        "slab_B": _side(status="defined", directions=np.eye(2).tolist()),
    }
    analysis = _analysis(monkeypatch, strain_info=strain_info)

    result = analysis.get_principal_strain_directions_crystallographic(
        "proto:test",
        max_index=2,
        max_angular_error_deg=1.0e-6,
    )

    assert result["direction_analysis_version"] == 2
    assert result["slab_A"]["formatted"][0] == "[1 1 0]"
    assert result["slab_A"]["low_index_directions"][0] == [1, 1, 0]
    assert result["slab_B"]["formatted"][0] == "[1 0 0]"
    assert result["slab_A"]["conventional_cell_formula"] == "Cu₂"


def test_service_withholds_axes_for_degenerate_eigenspace(monkeypatch) -> None:
    strain_info = {
        "alpha": 0.5,
        "alpha_convention": (
            "alpha=0 leaves A unstrained; alpha=1 leaves B unstrained"
        ),
        "slab_A": _side(status="degenerate", directions=None),
        "slab_B": _side(status="near_degenerate", directions=None),
    }
    analysis = _analysis(monkeypatch, strain_info=strain_info)

    result = analysis.get_principal_strain_directions_crystallographic(
        "proto:test"
    )

    for side in ("slab_A", "slab_B"):
        assert result[side]["directions_conventional"] is None
        assert result[side]["low_index_directions"] is None
        assert result[side]["formatted"] is None
        assert result[side]["principal_eigenspace_projector"] == [
            [1.0, 0.0],
            [0.0, 1.0],
        ]
