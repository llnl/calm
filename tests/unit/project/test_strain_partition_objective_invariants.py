"""Contracts for persisted strain-scan objective construction."""

from __future__ import annotations

from importlib.machinery import ModuleSpec

import importlib.util
import sys
import types
from types import SimpleNamespace

import numpy as np
import pytest


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except ValueError:
        return name in sys.modules


def _module_stub(name: str) -> types.ModuleType:
    module = types.ModuleType(name)
    module.__spec__ = ModuleSpec(name, loader=None)
    return module


_INSERTED_STUBS: list[str] = []
if not _module_available("ase"):
    ase_stub = _module_stub("ase")

    class Atoms:  # pragma: no cover - import stub only
        pass

    ase_stub.Atoms = Atoms
    sys.modules["ase"] = ase_stub
    _INSERTED_STUBS.append("ase")

try:
    from calm.project.application.followups import interface_energy
finally:
    for _module_name in _INSERTED_STUBS:
        sys.modules.pop(_module_name, None)


@pytest.fixture(autouse=True)
def _stub_partition_geometry(monkeypatch: pytest.MonkeyPatch) -> None:
    def geometry(_prototype, *, alpha: float):
        total = (-0.02, 0.04)
        side_a = tuple(sorted(float(alpha) * value for value in total))
        side_b = tuple(sorted(-(1.0 - float(alpha)) * value for value in total))
        return SimpleNamespace(
            X=np.diag([2.0, 3.0]),
            side_a_principal_log_strains=side_a,
            side_b_principal_log_strains=side_b,
            side_a_max_abs_principal_log_strain=max(abs(value) for value in side_a),
            side_b_max_abs_principal_log_strain=max(abs(value) for value in side_b),
            side_a_airm_distance=2.0 * sum(value * value for value in side_a) ** 0.5,
            side_b_airm_distance=2.0 * sum(value * value for value in side_b) ** 0.5,
        )

    monkeypatch.setattr(
        interface_energy,
        "_strain_partition_geometry",
        geometry,
    )


def _prototype_record(payload: dict[str, object]) -> SimpleNamespace:
    metrics = payload["metrics"]
    assert isinstance(metrics, dict)
    pareto = payload.get("pareto")
    return SimpleNamespace(
        payload=payload,
        slab_a_uid_full=payload["slab_a_uid"],
        slab_b_uid_full=payload["slab_b_uid"],
        match_score=metrics["match_score"],
        hencky_norm=0.5 * float(metrics["d_cell"]),
        interface_area=metrics["interface_area_A2"],
        natoms=metrics["n_atoms_interface"],
        is_pareto=False if pareto is None else pareto["is_member"],
        pareto_rank=None if pareto is None else pareto["rank"],
    )


def test_persisted_supercell_gauge_accepts_reflection() -> None:
    reflected = np.diag([1.0, -1.0])
    embedded = interface_energy._orthogonal_gauge_3d("R", reflected)

    assert np.array_equal(embedded[:2, :2], reflected)
    assert np.linalg.det(embedded) == pytest.approx(-1.0)

    with pytest.raises(ValueError, match="must be orthogonal"):
        interface_energy._orthogonal_gauge_3d(
            "R",
            np.array([[1.0, 0.1], [0.0, 1.0]]),
        )


def test_persisted_builder_forwards_supercell_rotations(
    monkeypatch,
    prototype_payload_factory,
) -> None:
    angle = np.deg2rad(20.0)
    rotation_a = np.array(
        [[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]]
    )
    rotation_b = rotation_a.T
    payload = prototype_payload_factory(include_supercells=True, include_pareto=False)
    payload["supercell_a"]["R_sup"] = rotation_a.tolist()
    payload["supercell_b"]["R_sup"] = rotation_b.tolist()
    record = _prototype_record(payload)
    slabs = {
        "slab:a": SimpleNamespace(atoms=object()),
        "slab:b": SimpleNamespace(atoms=object()),
    }
    uow = SimpleNamespace(
        prototypes=SimpleNamespace(get_by_uid_full=lambda _uid: record),
        slabs=SimpleNamespace(get_by_uid_full=lambda uid: slabs[uid]),
    )
    captured = {}

    def fake_build(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return "atoms"

    monkeypatch.setattr(interface_energy, "_build_simple_interface", fake_build)

    result = interface_energy.build_interface_from_prototype_with_strain(
        uow,
        "proto:1",
        alpha=0.4,
    )

    assert result == "atoms"
    assert np.allclose(captured["kwargs"]["R_A"], rotation_a)
    assert np.allclose(captured["kwargs"]["R_B"], rotation_b)


def test_persisted_builder_rejects_fractional_supercell_maps(
    monkeypatch,
    prototype_payload_factory,
) -> None:
    payload = prototype_payload_factory(include_supercells=True, include_pareto=False)
    payload["supercell_a"]["N_tot"] = [[1.0, 0.5], [0.0, 1.0]]
    record = _prototype_record(payload)
    slabs = {
        "slab:a": SimpleNamespace(atoms=object()),
        "slab:b": SimpleNamespace(atoms=object()),
    }
    uow = SimpleNamespace(
        prototypes=SimpleNamespace(get_by_uid_full=lambda _uid: record),
        slabs=SimpleNamespace(get_by_uid_full=lambda uid: slabs[uid]),
    )
    build_calls = 0

    def fake_build(*args, **kwargs):
        nonlocal build_calls
        build_calls += 1
        return "atoms"

    monkeypatch.setattr(interface_energy, "_build_simple_interface", fake_build)

    with pytest.raises(ValueError, match="exact integers"):
        interface_energy.build_interface_from_prototype_with_strain(
            uow,
            "proto:1",
            alpha=0.5,
        )

    assert build_calls == 0


def test_persisted_builder_rejects_incomplete_current_payload_before_build(
    monkeypatch,
    prototype_payload_factory,
) -> None:
    payload = prototype_payload_factory(
        include_supercells=True,
        include_pareto=False,
    )
    payload.pop("pair_identity")
    record = _prototype_record(payload)
    slabs = {
        "slab:a": SimpleNamespace(atoms=object()),
        "slab:b": SimpleNamespace(atoms=object()),
    }
    uow = SimpleNamespace(
        prototypes=SimpleNamespace(get_by_uid_full=lambda _uid: record),
        slabs=SimpleNamespace(get_by_uid_full=lambda uid: slabs[uid]),
    )
    build_calls = 0

    def fake_build(*args, **kwargs):
        nonlocal build_calls
        build_calls += 1
        return "atoms"

    monkeypatch.setattr(interface_energy, "_build_simple_interface", fake_build)

    with pytest.raises(ValueError, match="pair_identity"):
        interface_energy.build_interface_from_prototype_with_strain(
            uow,
            "proto:1",
            alpha=0.5,
        )

    assert build_calls == 0


def test_gamma_objective_uses_scanned_alpha_and_build_parameters(
    monkeypatch,
) -> None:
    class FakeAtoms:
        def __init__(self) -> None:
            self.calc = None

        def get_potential_energy(self):
            return 12.0

        def get_cell(self):
            return np.diag([2.0, 3.0, 10.0])

    prototype = SimpleNamespace(
        slab_a=SimpleNamespace(bulk=object()),
        slab_b=SimpleNamespace(bulk=object()),
    )
    load_calls = 0

    def load(*args, **kwargs):
        nonlocal load_calls
        load_calls += 1
        return prototype

    monkeypatch.setattr(interface_energy, "load_interface_prototype", load)
    monkeypatch.setattr(
        interface_energy,
        "_build_loaded_interface_prototype",
        lambda *args, **kwargs: FakeAtoms(),
    )

    recorded = {}
    pipeline = types.ModuleType("calm.interface.pipeline")

    def compute_strain_state(prototype, model):
        recorded["prototype"] = prototype
        recorded["alpha"] = model.alpha
        return "strain-state"

    def build_interface(prototype, strain, build):
        recorded["translation"] = build.translation_frac
        recorded["z_padding"] = build.z_padding
        recorded["vacuum_padding"] = build.vacuum_padding
        return "interface-object"

    def compute_interfacial_energy(interface, calc, config):
        recorded["energy_config"] = config
        return SimpleNamespace(
            gamma_eV_per_A2=0.25,
            gamma_J_per_m2=4.0,
            n_fu_slab_A=2,
            n_fu_slab_B=3,
            mu_bulk_A_eV_per_fu=-1.0,
            mu_bulk_B_eV_per_fu=-2.0,
        )

    pipeline.compute_strain_state = compute_strain_state
    pipeline.build_interface = build_interface
    pipeline.compute_interfacial_energy = compute_interfacial_energy
    monkeypatch.setitem(sys.modules, "calm.interface.pipeline", pipeline)

    uow = SimpleNamespace()
    config = object()
    result = interface_energy.compute_strain_scan_energy_point(
        uow,
        "proto:1",
        alpha=0.73,
        calc_spec=object(),
        translation_frac=(0.2, 0.4),
        z_padding=2.5,
        calc=object(),
        energy_config=config,
    )

    assert load_calls == 1
    assert recorded["prototype"].slab_a.bulk is not None
    assert recorded["alpha"] == pytest.approx(0.73)
    assert recorded["translation"] == pytest.approx((0.2, 0.4))
    assert recorded["z_padding"] == pytest.approx(2.5)
    assert recorded["vacuum_padding"] == pytest.approx(2.5)
    assert recorded["energy_config"] is config
    assert result["gamma_eV_per_A2"] == pytest.approx(0.25)
    assert result["interface_area_A2"] == pytest.approx(6.0)
    assert result["side_a_principal_log_strains"] == pytest.approx([-0.0146, 0.0292])
    assert result["side_b_principal_log_strains"] == pytest.approx([-0.0108, 0.0054])
    assert result["side_a_airm_distance"] + result[
        "side_b_airm_distance"
    ] == pytest.approx(2.0 * np.sqrt(0.02**2 + 0.04**2))
