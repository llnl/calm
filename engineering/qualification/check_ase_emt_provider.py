#!/usr/bin/env python3
"""Generate end-to-end qualification evidence for the ASE EMT CPU baseline."""

from __future__ import annotations

import argparse
import json
import math
import platform
import shutil
import sys
import time
import traceback
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Any, Callable, Mapping


EVIDENCE_SCHEMA_VERSION = "calm.ase_emt_provider_evidence.v1"
REQUIRED_EVIDENCE = ("construction", "relaxation", "energy", "provenance")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _package_version(name: str) -> str | None:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def _environment() -> dict[str, Any]:
    return {
        "platform": platform.system(),
        "platform_release": platform.release(),
        "architecture": platform.machine(),
        "python": platform.python_version(),
        "python_executable": sys.executable,
        "packages": {
            name: _package_version(name)
            for name in ("calm", "ase", "numpy", "sqlalchemy")
        },
    }


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _calculator_spec():
    from calm.calculators import CalculatorSpec

    return CalculatorSpec(
        family="ase",
        model="EMT",
        device="cpu",
    )


def _perturbed_aluminum_cell():
    from ase.build import bulk

    atoms = bulk("Al", "fcc", a=4.05, cubic=True)
    atoms.positions[0] += (0.05, 0.0, 0.0)
    return atoms


def _maximum_force(forces: Any) -> float:
    import numpy as np

    array = np.asarray(forces, dtype=float)
    if array.size == 0:
        return 0.0
    norms = np.linalg.norm(array, axis=1)
    return float(norms.max())


def _assert_finite(name: str, value: float) -> None:
    if not math.isfinite(float(value)):
        raise AssertionError(f"{name} must be finite; observed {value!r}")


def _identity_paths(
    value: Any,
    *,
    path: str = "root",
) -> list[str]:
    matches: list[str] = []
    if isinstance(value, Mapping):
        family = str(value.get("family") or "").strip().lower()
        model = str(value.get("model") or "").strip().upper()
        device = str(value.get("device") or "cpu").strip().lower()
        if family == "ase" and model == "EMT" and device == "cpu":
            matches.append(path)
        for key, item in value.items():
            matches.extend(_identity_paths(item, path=f"{path}.{key}"))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            matches.extend(_identity_paths(item, path=f"{path}[{index}]"))
    return matches


def _check_construction(_work_root: Path) -> dict[str, Any]:
    from calm.calculators import make_calculator

    spec = _calculator_spec()
    calculator = make_calculator(spec)
    calculator_type = type(calculator)
    if calculator_type.__name__ != "EMT":
        raise AssertionError(
            "ASE provider did not construct EMT; observed "
            f"{calculator_type.__module__}.{calculator_type.__name__}"
        )
    return {
        "spec": spec.to_dict(),
        "spec_fingerprint": spec.fingerprint(),
        "calculator_class": (
            f"{calculator_type.__module__}.{calculator_type.__name__}"
        ),
    }


def _check_energy(_work_root: Path) -> dict[str, Any]:
    from calm.calculators import make_calculator

    atoms = _perturbed_aluminum_cell()
    atoms.calc = make_calculator(_calculator_spec())
    energy = float(atoms.get_potential_energy())
    max_force = _maximum_force(atoms.get_forces())
    _assert_finite("potential energy", energy)
    _assert_finite("maximum force", max_force)
    return {
        "structure": "Al fcc conventional cell with one 0.05 A displacement",
        "n_atoms": len(atoms),
        "total_energy_eV": energy,
        "max_force_eV_per_A": max_force,
    }


def _check_relaxation(_work_root: Path) -> dict[str, Any]:
    import numpy as np

    from calm import Material, Potential

    atoms = _perturbed_aluminum_cell()
    initial_positions = np.asarray(atoms.positions, dtype=float).copy()
    material = Material.from_ase(atoms, name="Al_perturbed")
    optimized = material.optimize(
        potential=Potential(family="ase", model="EMT", device="cpu"),
        fmax=0.05,
        steps=100,
        relax_cell=False,
        name="Al_relaxed",
    )
    final_atoms = optimized.to_ase()
    final_energy = float(final_atoms.get_potential_energy())
    max_force = _maximum_force(final_atoms.get_forces())
    displacement = float(
        np.linalg.norm(np.asarray(final_atoms.positions) - initial_positions)
    )
    _assert_finite("relaxed total energy", final_energy)
    _assert_finite("relaxed maximum force", max_force)
    if max_force > 0.0505:
        raise AssertionError(
            "ASE EMT relaxation did not satisfy fmax=0.05 eV/A; "
            f"observed {max_force:.8f} eV/A"
        )
    if displacement <= 1.0e-10:
        raise AssertionError("ASE EMT relaxation did not update atomic positions")
    return {
        "optimizer": "ASE BFGS through Material.optimize",
        "fmax_eV_per_A": 0.05,
        "step_limit": 100,
        "final_total_energy_eV": final_energy,
        "final_max_force_eV_per_A": max_force,
        "position_displacement_norm_A": displacement,
    }


def _check_provenance(work_root: Path) -> dict[str, Any]:
    from calm import Material, Potential, open_project

    project_path = work_root / "ase-emt-provider.calm"
    project = open_project(project_path)
    material = Material.from_ase(
        _perturbed_aluminum_cell(),
        name="Al_provider_input",
    )
    optimized = project.optimize_material(
        material,
        potential=Potential(family="ase", model="EMT", device="cpu"),
        fmax=0.05,
        steps=100,
        relax_cell=False,
        name="Al_EMT_optimized",
    )
    if optimized.uid_full is None:
        raise AssertionError("optimized material was not assigned a persistent UID")

    reopened = open_project(project_path)
    persisted = reopened.material("Al_EMT_optimized")
    if persisted.uid_full != optimized.uid_full:
        raise AssertionError(
            "reopened optimized material identity does not match the saved record"
        )

    manifest = reopened.write_reproducibility_manifest(overwrite=True)
    verification = reopened.verify_reproducibility_manifest()
    if not verification.ok:
        verification.raise_for_errors()
    payload = manifest.to_dict()
    configuration_matches = _identity_paths(
        payload.get("configuration"),
        path="manifest.configuration",
    )
    backend_matches = _identity_paths(
        payload.get("backends"),
        path="manifest.backends",
    )
    if not configuration_matches:
        raise AssertionError(
            "reproducibility manifest configuration does not retain ase/EMT/cpu"
        )
    if not backend_matches:
        raise AssertionError(
            "reproducibility manifest backend inventory does not retain ase/EMT/cpu"
        )
    return {
        "project_path": str(project_path.resolve()),
        "optimized_material_uid": persisted.uid_full,
        "optimized_material_id": persisted.id_short,
        "manifest_snapshot_id": manifest.snapshot_id,
        "manifest_verified": verification.ok,
        "configuration_identity_paths": configuration_matches,
        "backend_identity_paths": backend_matches,
    }


def _run_check(
    evidence: str,
    function: Callable[[Path], dict[str, Any]],
    *,
    work_root: Path,
) -> dict[str, Any]:
    started_at = _utc_now()
    started = time.monotonic()
    try:
        details = function(work_root)
    except Exception as exc:
        result = {
            "evidence": evidence,
            "status": "failed",
            "started_at": started_at,
            "finished_at": _utc_now(),
            "duration_seconds": round(time.monotonic() - started, 6),
            "error_type": type(exc).__name__,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }
    else:
        result = {
            "evidence": evidence,
            "status": "passed",
            "started_at": started_at,
            "finished_at": _utc_now(),
            "duration_seconds": round(time.monotonic() - started, 6),
            "details": details,
        }
    print(f"[{result['status'].upper()}] {evidence}")
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output = args.output.expanduser().resolve()
    work_root = args.work_root.expanduser().resolve()
    if work_root.exists():
        shutil.rmtree(work_root)
    work_root.mkdir(parents=True)

    report: dict[str, Any] = {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "started_at": _utc_now(),
        "provider": {
            "family": "ase",
            "model": "EMT",
            "device": "cpu",
            "support_scope": "ASE EMT CPU baseline provider plumbing only",
        },
        "required_evidence": list(REQUIRED_EVIDENCE),
        "environment": _environment(),
        "work_root": str(work_root),
        "checks": [],
    }
    checks = (
        ("construction", _check_construction),
        ("energy", _check_energy),
        ("relaxation", _check_relaxation),
        ("provenance", _check_provenance),
    )
    for evidence, function in checks:
        report["checks"].append(
            _run_check(evidence, function, work_root=work_root)
        )

    observed = {
        item["evidence"]
        for item in report["checks"]
        if item["status"] == "passed"
    }
    provider_qualified = observed == set(REQUIRED_EVIDENCE)
    report.update(
        status="passed" if provider_qualified else "failed",
        provider_qualified=provider_qualified,
        finished_at=_utc_now(),
    )
    _write_json(output, report)
    print(f"Wrote ASE EMT provider evidence: {output}")
    return 0 if provider_qualified else 1


if __name__ == "__main__":
    raise SystemExit(main())
