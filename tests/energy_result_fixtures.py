"""Exact-current energy-result payload fixtures for tests.

These builders intentionally spell out the persisted contracts instead of
calling production canonicalizers.  Tests therefore exercise the public and
repository readers against the same versioned shapes emitted by workflows.
"""

from __future__ import annotations

from typing import Any

from calm.interface.energy.contract import EV_PER_A2_TO_J_PER_M2


def raw_energy_payload(
    energy_eV: float,
    *,
    backend_name: str = "deterministic",
    backend_identity: dict[str, Any] | None = None,
    settings: dict[str, Any] | None = None,
    interface_area_A2: float | None = 10.0,
    n_steps: int = 1,
    artifact_refs: list[str] | None = None,
    workflow_metadata: dict[str, Any] | None = None,
    summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    identity = dict(backend_identity or {"name": backend_name})
    identity.setdefault("name", backend_name)
    return {
        "schema": "calm.raw_energy_result",
        "version": 1,
        "result_stage": "energy_evaluated",
        "quantity": "total_energy",
        "energy_eV": float(energy_eV),
        "n_steps": int(n_steps),
        "interface_area_A2": interface_area_A2,
        "area_source": (
            "authoritative_interface_cell"
            if interface_area_A2 is not None
            else None
        ),
        "backend": {
            "name": backend_name,
            "identity": identity,
            "settings": dict(settings or {"mode": "single_point"}),
        },
        "workflow_metadata": dict(workflow_metadata or {}),
        "artifact_refs": list(artifact_refs or []),
        "summary": dict(summary or {}),
    }


def failed_raw_energy_payload(
    *,
    backend_name: str = "deterministic",
    backend_identity: dict[str, Any] | None = None,
    settings: dict[str, Any] | None = None,
    message: str = "backend failed",
) -> dict[str, Any]:
    identity = dict(backend_identity or {"name": backend_name})
    identity.setdefault("name", backend_name)
    return {
        "schema": "calm.raw_energy_result",
        "version": 1,
        "result_stage": "energy_failed",
        "quantity": "total_energy",
        "backend": {
            "name": backend_name,
            "identity": identity,
            "settings": dict(settings or {"mode": "single_point"}),
        },
        "workflow_metadata": {},
        "failure": {
            "message": message,
            "exception_type": "RuntimeError",
            "module": "builtins",
        },
    }


def reference_energy_payload(
    *,
    reference_uid_full: str,
    reference_kind: str,
    formula_id: str,
    energy_eV: float,
    energy_eV_per_formula_unit: float | None = None,
    reference_formula_units: int | None = None,
    interface_formula_units: int | None = None,
    backend_name: str = "deterministic",
    backend_identity: dict[str, Any] | None = None,
    settings: dict[str, Any] | None = None,
    reference_area_A2: float = 10.0,
    source_bulk_uid_full: str | None = "bulk:1",
    source_slab_uid_full: str | None = "slab:1",
    structure_fingerprint: str | None = "structure:fingerprint",
    relaxed: bool = False,
    workflow_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    side = reference_kind.rsplit("_", 1)[-1]
    identity = dict(backend_identity or {"name": backend_name})
    identity.setdefault("name", backend_name)
    metadata: dict[str, Any] = {
        "reference_formula_units": reference_formula_units,
        "interface_formula_units": interface_formula_units,
        "source_bulk_uid_full": source_bulk_uid_full,
        "source_slab_uid_full": source_slab_uid_full,
        "structure_fingerprint": structure_fingerprint,
        "reference_area_A2": float(reference_area_A2),
    }
    relaxation = None
    if relaxed:
        engine = {
            "algorithm": "ase_bfgs_fixed_cell_surface_relaxation_v1",
            "optimizer": "ASE.BFGS",
            "software_versions": {
                "ase": "test",
                "numpy": "test",
                "scipy": "test",
            },
        }
        identity["reference_relaxation_engine"] = engine
        metadata.update(
            {
                "reference_protocol": (
                    "cleaved_fixed_cell_independent_relaxation_v1"
                ),
                "source_interface_structure_fingerprint": (
                    "interface:fingerprint"
                ),
            }
        )
        relaxation = {
            "settings": {
                "protocol": "cleaved_fixed_cell_independent_relaxation_v1",
                "optimizer": "BFGS",
                "fmax": 0.05,
                "steps": 500,
                "relax_cell": False,
            },
            "summary": {"converged": True, "relax_cell": False},
            "final_structure_fingerprint": f"final:{reference_uid_full}",
        }
    return {
        "schema": "calm.reference_energy_result",
        "version": 1,
        "result_stage": "reference_evaluated",
        "reference": {
            "uid_full": reference_uid_full,
            "kind": reference_kind,
            "side": side,
            "formula_id": formula_id,
            "metadata": metadata,
        },
        "energy": {
            "total_eV": float(energy_eV),
            "per_formula_unit_eV": energy_eV_per_formula_unit,
            "n_steps": 0,
        },
        "backend": {
            "name": backend_name,
            "identity": identity,
            "settings": dict(settings or {"mode": "single_point"}),
        },
        "relaxation": relaxation,
        "workflow_metadata": dict(workflow_metadata or {}),
        "artifact_refs": [],
        "summary": {},
    }


def failed_reference_energy_payload(
    *,
    reference_uid_full: str,
    reference_kind: str,
    formula_id: str,
    message: str = "backend failed",
) -> dict[str, Any]:
    payload = reference_energy_payload(
        reference_uid_full=reference_uid_full,
        reference_kind=reference_kind,
        formula_id=formula_id,
        energy_eV=0.0,
        energy_eV_per_formula_unit=(
            0.0 if reference_kind.startswith("strained_bulk_") else None
        ),
        reference_formula_units=(
            1 if reference_kind.startswith("strained_bulk_") else None
        ),
        interface_formula_units=(
            1 if reference_kind.startswith("strained_bulk_") else None
        ),
        relaxed=formula_id == "work_of_adhesion_relaxed_surfaces",
    )
    return {
        "schema": payload["schema"],
        "version": payload["version"],
        "result_stage": "reference_failed",
        "reference": payload["reference"],
        "backend": payload["backend"],
        "relaxation": payload["relaxation"],
        "workflow_metadata": payload["workflow_metadata"],
        "failure": {
            "message": message,
            "exception_type": "RuntimeError",
            "module": "builtins",
        },
    }


def thermodynamic_payload(
    *,
    raw_energy_followup_uid: str,
    value_eV_per_A2: float,
    formula_id: str = "interface_excess_strained_bulk",
    quantity: str = "interface_excess_energy",
    area_A2: float = 10.0,
    n_interfaces: int = 2,
    reference_mode: str | None = None,
    reference_run_uid_full: str | None = None,
    area_source_status: str = "authoritative_interface_cell",
    references: dict[str, Any] | None = None,
    components: dict[str, Any] | None = None,
    calculator_compatibility: dict[str, Any] | None = None,
) -> dict[str, Any]:
    compatibility = dict(
        calculator_compatibility
        or {
            "status": "verified",
            "raw": {
                "backend": "deterministic",
                "identity": {"name": "deterministic"},
                "settings": {"mode": "single_point"},
                "interface_area_A2": float(area_A2),
            },
            "reference": {
                "backend": "deterministic",
                "identity": {"name": "deterministic"},
                "settings": {"mode": "single_point"},
                "interface_area_A2": float(area_A2),
                "relaxation": None,
            },
        }
    )
    calculated = compatibility.get("status") == "verified"
    mode = reference_mode or ("by_target_uid" if calculated else "static")
    run_uid = reference_run_uid_full
    if calculated and run_uid is None:
        run_uid = "run:reference"

    if formula_id == "interface_excess_strained_bulk":
        reference_values: dict[str, Any] = {
            "bulk_a_eV_per_formula_unit": -1.0,
            "bulk_b_eV_per_formula_unit": -2.0,
            "n_formula_units_a": 1,
            "n_formula_units_b": 1,
        }
        if references and references.get("status") not in {"resolved", "unresolved"}:
            reference_values.update(references)
        reference_kinds = ("strained_bulk_a", "strained_bulk_b")
        bulk_a = (
            float(reference_values["bulk_a_eV_per_formula_unit"])
            * int(reference_values["n_formula_units_a"])
        )
        bulk_b = (
            float(reference_values["bulk_b_eV_per_formula_unit"])
            * int(reference_values["n_formula_units_b"])
        )
        reference_total = bulk_a + bulk_b
        excess = float(value_eV_per_A2) * float(area_A2) * int(n_interfaces)
        interface_total = reference_total + excess
        component_values = {
            "interface_total_energy_eV": interface_total,
            "bulk_a_reference_total_eV": bulk_a,
            "bulk_b_reference_total_eV": bulk_b,
            "reference_total_eV": reference_total,
            "excess_energy_eV": excess,
        }
    else:
        reference_values = {
            "surface_a_total_energy_eV": -1.0,
            "surface_b_total_energy_eV": -2.0,
        }
        if references and references.get("status") not in {"resolved", "unresolved"}:
            reference_values.update(references)
        reference_kinds = (
            ("relaxed_surface_a", "relaxed_surface_b")
            if formula_id == "work_of_adhesion_relaxed_surfaces"
            else ("isolated_surface_a", "isolated_surface_b")
        )
        surface_a = float(reference_values["surface_a_total_energy_eV"])
        surface_b = float(reference_values["surface_b_total_energy_eV"])
        numerator = float(value_eV_per_A2) * float(area_A2) * int(n_interfaces)
        interface_total = surface_a + surface_b - numerator
        numerator_key = (
            "adhesion_energy_eV"
            if formula_id == "work_of_adhesion_relaxed_surfaces"
            else "separation_energy_eV"
        )
        component_values = {
            "interface_total_energy_eV": interface_total,
            "surface_a_total_energy_eV": surface_a,
            "surface_b_total_energy_eV": surface_b,
            numerator_key: numerator,
        }

    if references and references.get("status") in {"resolved", "unresolved"}:
        reference_bundle = dict(references)
    else:
        reference_bundle = {
            "status": "resolved",
            "source_kind": "calculated" if calculated else "manual",
            "result_uids": (
                {
                    kind: f"followup:reference:{kind}"
                    for kind in reference_kinds
                }
                if calculated
                else {}
            ),
            "values": reference_values,
            "metadata": {},
        }
    if components:
        component_values.update(components)

    return {
        "schema": "calm.thermodynamic_result",
        "version": 1,
        "result_stage": "thermodynamic_derived",
        "source": {
            "raw_energy_followup_uid": raw_energy_followup_uid,
            "reference_mode": mode,
            "reference_run_uid_full": run_uid,
        },
        "quantity": {
            "name": quantity,
            "formula_id": formula_id,
            "value_eV_per_A2": float(value_eV_per_A2),
            "value_J_per_m2": float(value_eV_per_A2) * EV_PER_A2_TO_J_PER_M2,
        },
        "normalization": {
            "area_A2": float(area_A2),
            "area_source_status": area_source_status,
            "n_interfaces": int(n_interfaces),
        },
        "convention": {
            "formula": formula_id,
            "quantity": quantity,
            "n_interfaces": int(n_interfaces),
            "area_source": "authoritative_interface_area",
        },
        "references": reference_bundle,
        "components": component_values,
        "calculator_compatibility": compatibility,
        "units": {
            "primary": "eV/angstrom^2",
            "secondary": "J/m^2",
        },
    }
