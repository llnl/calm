from __future__ import annotations

from types import SimpleNamespace

import pytest

from calm.project.runtime.workspace import Workspace


_MISSING = object()


def _valid_interface_atoms():
    import numpy as np

    identity = np.eye(3).tolist()
    return SimpleNamespace(
        cell=SimpleNamespace(array=np.diag([2.0, 2.0, 8.0])),
        info={
            "calm:slab_deformation_accounting": {
                "policy": "composed_slab_deformation",
                "version": 1,
                "lower": {
                    "F_construction_slab": identity,
                    "F_interface_slab": identity,
                    "F_total_slab": identity,
                },
                "upper": {
                    "F_construction_slab": identity,
                    "F_interface_slab": identity,
                    "F_total_slab": identity,
                },
            }
        },
    )


def _workspace(monkeypatch, interface, *, atoms=_MISSING):
    workspace = object.__new__(Workspace)
    if atoms is _MISSING:
        atoms = _valid_interface_atoms()
    calls: list[tuple[str, object]] = []

    monkeypatch.setattr(
        workspace,
        "get_derived_interface",
        lambda identifier: interface,
    )
    monkeypatch.setattr(
        workspace,
        "get_derived_interface_atoms",
        lambda identifier: calls.append(("artifact", identifier)) or atoms,
    )

    def build(prototype, **kwargs):
        calls.append((prototype, kwargs))
        return SimpleNamespace(atoms=atoms)

    monkeypatch.setattr(workspace, "build_interface_from_prototype", build)
    return workspace, atoms, calls


def test_materialize_derived_interface_atoms_loads_present_artifact(monkeypatch):
    interface = SimpleNamespace(
        uid_full="iface:artifact",
        atoms_artifact_uid="artifact:1",
        stage="relaxed",
    )
    workspace, atoms, calls = _workspace(monkeypatch, interface)

    assert workspace.materialize_derived_interface_atoms("i_artifact") is atoms
    assert calls == [("artifact", "iface:artifact")]


def test_materialize_derived_interface_atoms_reconstructs_exact_spec(monkeypatch):
    interface = SimpleNamespace(
        uid_full="iface:spec",
        atoms_artifact_uid=None,
        stage="registry_refined",
        prototype_uid_full="proto:1",
        strain_alpha=0.25,
        registry_shift_frac_a=(0.1, 0.2),
        z_padding=2.5,
        vacuum=18.0,
    )
    workspace, atoms, calls = _workspace(monkeypatch, interface)

    assert workspace.materialize_derived_interface_atoms("i_spec") is atoms
    assert calls == [
        (
            "proto:1",
            {
                "alpha": 0.25,
                "translation_frac": (0.1, 0.2),
                "z_padding": 2.5,
                "vacuum": 18.0,
            },
        )
    ]


def test_materialize_derived_interface_atoms_canonicalizes_shift_override(monkeypatch):
    interface = SimpleNamespace(
        uid_full="iface:spec",
        atoms_artifact_uid=None,
        stage="strain_partitioned",
        prototype_uid_full="proto:1",
        strain_alpha=0.75,
        registry_shift_frac_a=(0.0, 0.0),
        z_padding=1.5,
        vacuum=None,
    )
    workspace, atoms, calls = _workspace(monkeypatch, interface)

    assert (
        workspace.materialize_derived_interface_atoms(
            "i_spec",
            registry_shift_frac_a=(1.1, -0.2),
        )
        is atoms
    )
    assert calls[0][1]["translation_frac"] == pytest.approx((0.1, 0.8))


def test_materialize_derived_interface_atoms_rejects_unreconstructible_stage(
    monkeypatch,
):
    interface = SimpleNamespace(
        uid_full="iface:relaxed",
        atoms_artifact_uid=None,
        stage="relaxed",
    )
    workspace, _atoms, calls = _workspace(monkeypatch, interface)

    with pytest.raises(KeyError, match="cannot be reconstructed"):
        workspace.materialize_derived_interface_atoms("i_relaxed")
    assert calls == []


def test_materialize_derived_interface_atoms_rejects_malformed_deformation_metadata(
    monkeypatch,
):
    import numpy as np

    class Cell:
        def __init__(self):
            self.array = np.diag([2.0, 2.0, 8.0])

    atoms = SimpleNamespace(
        cell=Cell(),
        info={
            "calm:slab_deformation_accounting": {
                "policy": "composed_slab_deformation",
                "version": 1,
                "lower": {
                    "F_construction_slab": np.eye(3).tolist(),
                    "F_interface_slab": np.eye(3).tolist(),
                    "F_total_slab": np.diag([2.0, 1.0, 1.0]).tolist(),
                },
                "upper": {
                    "F_construction_slab": np.eye(3).tolist(),
                    "F_interface_slab": np.eye(3).tolist(),
                    "F_total_slab": np.eye(3).tolist(),
                },
            }
        },
    )
    interface = SimpleNamespace(
        uid_full="iface:spec",
        atoms_artifact_uid=None,
        stage="registry_refined",
        prototype_uid_full="proto:1",
        strain_alpha=0.25,
        registry_shift_frac_a=(0.1, 0.2),
        z_padding=2.5,
        vacuum=18.0,
    )
    workspace, _atoms, _calls = _workspace(monkeypatch, interface, atoms=atoms)

    with pytest.raises(ValueError, match="must equal"):
        workspace.materialize_derived_interface_atoms("i_spec")


def test_materialize_derived_interface_atoms_requires_source_deformation_metadata(
    monkeypatch,
):
    import numpy as np

    atoms = SimpleNamespace(
        cell=SimpleNamespace(array=np.diag([2.0, 2.0, 8.0])),
        info={},
    )
    interface = SimpleNamespace(
        uid_full="iface:spec",
        atoms_artifact_uid=None,
        stage="built",
        prototype_uid_full="proto:1",
        strain_alpha=0.5,
        registry_shift_frac_a=(0.0, 0.0),
        z_padding=2.0,
        vacuum=15.0,
    )
    workspace, _atoms, _calls = _workspace(monkeypatch, interface, atoms=atoms)

    with pytest.raises(ValueError, match="accounting is required"):
        workspace.materialize_derived_interface_atoms("i_spec")
