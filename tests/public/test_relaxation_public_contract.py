from __future__ import annotations

import inspect
from dataclasses import fields

import calm
from calm.public.collections.interfaces import InterfaceCollection
from calm.public.records.search import PersistedInterfaceSearch
from calm.public.records.persistence import ProjectRelaxationResult, RecordAuthority
from calm.public.project import Project
from calm.public.inputs.settings import RelaxSettings


def test_relax_settings_are_operational_and_top_level_public() -> None:
    assert calm.RelaxSettings is RelaxSettings
    assert {field.name for field in fields(RelaxSettings)} == {
        "fmax",
        "steps",
        "relax_cell",
    }

    settings = RelaxSettings(fmax=0.025, steps=120, relax_cell=True)
    assert settings.protocol == "ionic_cell_v1"
    assert settings.to_dict() == {
        "fmax": 0.025,
        "steps": 120,
        "relax_cell": True,
    }
    assert settings.to_stage_kwargs() == {
        "protocol": "ionic_cell_v1",
        "convergence": {"force_tol": 0.025},
        "max_steps": 120,
        "payload": {
            "relax_settings": {
                "fmax": 0.025,
                "steps": 120,
                "relax_cell": True,
            }
        },
    }


def test_relax_settings_reject_inert_or_invalid_values() -> None:
    assert "trajectory" not in inspect.signature(RelaxSettings).parameters

    for settings, expected in (
        (RelaxSettings(fmax=0.0), ValueError),
        (RelaxSettings(steps=0), ValueError),
        (RelaxSettings(relax_cell=1), TypeError),
    ):
        try:
            settings.validate()
        except expected:
            pass
        else:  # pragma: no cover - assertion helper
            raise AssertionError(f"{settings!r} did not raise {expected.__name__}")


def test_relaxation_result_is_typed_and_preserves_provenance() -> None:
    item = {
        "uid_full": "followup:relax",
        "id_short": "f_relax",
        "run_uid_full": "run:relax",
        "run_id_short": "r_relax",
        "prototype_uid_full": "proto:x",
        "target_uid_full": "iface:refined",
        "target_kind": "interface",
        "kind": "relaxation_stage",
        "status": "done",
        "best_energy": -12.5,
        "n_points": 17,
        "payload": {
            "relaxed_interface_uid": "iface:relaxed",
            "final_energy_eV": -12.5,
            "n_steps": 17,
            "converged": True,
            "max_force_eV_per_A": 0.019,
            "max_optimizer_residual": 0.019,
            "optimizer_reported_converged": True,
            "residual_satisfied": True,
            "convergence_certificate": {"termination_reason": "converged"},
            "backend_identity": {
                "name": "real",
                "algorithm": "ase_bfgs_interface_relaxation_v2",
            },
            "relaxation_backend": "real",
            "relaxation_settings": {
                "fmax": 0.02,
                "steps": 100,
                "relax_cell": False,
            },
            "artifact_refs": ["artifact:summary", "artifact:structure"],
        },
        "authority": "authoritative",
    }

    result = ProjectRelaxationResult.from_item(item)
    assert result.authority is RecordAuthority.AUTHORITATIVE
    assert result.succeeded
    assert result.target_uid_full == "iface:refined"
    assert result.relaxed_interface_uid == "iface:relaxed"
    assert result.final_energy_eV == -12.5
    assert result.max_force_eV_per_A == 0.019
    assert result.max_optimizer_residual == 0.019
    assert result.optimizer_reported_converged is True
    assert result.residual_satisfied is True
    assert result.termination_reason == "converged"
    assert result.backend_identity["algorithm"] == (
        "ase_bfgs_interface_relaxation_v2"
    )
    assert result.backend == "real"
    assert result.artifact_refs == ("artifact:summary", "artifact:structure")


def test_interface_collection_does_not_execute_relaxation() -> None:
    assert not hasattr(InterfaceCollection, "_relax")


def test_persisted_search_does_not_execute_relaxation() -> None:
    assert not hasattr(PersistedInterfaceSearch, "relax_interfaces")

def test_project_relaxation_surface_is_explicit() -> None:
    for name in {
        "relax_interfaces",
        "relaxed_interfaces",
        "relaxation_runs",
        "relaxation_results",
        "relaxation_result",
    }:
        assert hasattr(Project, name)

    parameters = inspect.signature(Project.relax_interfaces).parameters
    assert parameters["resume"].default is True
    assert parameters["partial_resume"].default is True
    assert parameters["on_error"].default == "raise"
    assert parameters["stage"].default == "registry_refined"
    assert parameters["backend"].default == "real"
