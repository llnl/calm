from __future__ import annotations

from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from typing import Any, Mapping

from calm.project.domain.contracts.relaxation import (
    INTERFACE_CELL_MASK,
    PERSISTED_CELL_FACTOR_MODE,
    PERSISTED_CELL_FILTER,
    PERSISTED_OPTIMIZER,
    canonical_relaxation_controls,
    max_vector_norm,
    validate_relaxation_result,
    validate_relaxed_structure_transition,
)
from calm.calculators.exceptions import (
    CalculatorError,
    CalculatorExecutionError,
    OptionalDependencyError,
)
from calm.exceptions import OptionalDependencyError as CALMOptionalDependencyError

from calm.serialization.regression import sha256_hex, deterministic_json
from calm.slab.oriented.cell_contract import (
    INTERFACE_DEFORMATION_ACCOUNTING_INFO_KEY,
    record_interface_relaxation_deformation,
    validate_interface_deformation_provenance,
)


def _installed_distribution_version(name: str) -> str | None:
    """Return one installed distribution version for run provenance."""

    try:
        return version(name)
    except PackageNotFoundError:
        return None


@dataclass
class RelaxationComputeResult:
    final_energy: float
    n_steps: int
    relaxed_params: dict[str, Any]
    summary: dict[str, Any]
    artifact_payloads: list[dict[str, Any]]
    relaxed_atoms: Any | None = None
    converged: bool = True
    max_force: float | None = None
    max_optimizer_residual: float | None = None
    optimizer_reported_converged: bool | None = None


class DeterministicRelaxationBackend:
    """Synthetic unchanged-structure backend for tests and dry workflows.

    This backend is never a scientific geometry optimizer.  It returns an
    unchanged structure and a deterministic pseudo-energy so persistence,
    resume, and provenance code can be exercised without ASE or a calculator.
    Callers must select it explicitly.
    """

    name = "deterministic"
    requires_target_atoms = False

    def identity(self, *, targets: Any, uow: Any | None = None) -> dict[str, Any]:
        del targets, uow
        return {
            "name": self.name,
            "algorithm": "sha256_unchanged_structure_v2",
            "scientific_authority": "synthetic_test_only",
            "optimizer": None,
        }

    def compute(
        self,
        *,
        run_uid: str,
        prototype_uid: str,
        target_uid: str,
        config: Mapping[str, Any],
        uow: Any | None = None,
    ) -> RelaxationComputeResult:
        del uow
        controls = canonical_relaxation_controls(
            protocol=config.get("protocol", "ionic_positions_v1"),
            convergence=config.get("convergence"),
            max_steps=config.get("max_steps", 1),
            relax_cell=config.get("relax_cell", False),
        )
        identity_config = {
            key: value for key, value in dict(config).items() if key != "target_atoms"
        }
        key = deterministic_json(
            {
                "run_uid": run_uid,
                "prototype_uid": prototype_uid,
                "target_uid": target_uid,
                "config": identity_config,
            },
            float_ndigits=12,
        )
        digest = sha256_hex(key.encode("utf-8"))
        energy = (int(digest[:8], 16) % 10000) / 1000.0
        relaxed_params = {
            "relaxation_backend": self.name,
            "scientific_authority": "synthetic_test_only",
            "configuration_changed": False,
            "final_energy_eV": energy,
            "n_steps": 0,
            "fmax_eV_per_A": controls.force_tolerance_eV_per_A,
            "relax_cell": controls.relax_cell,
            "optimizer": None,
            "converged": True,
            "termination_reason": "synthetic_unchanged_structure",
        }
        summary = dict(relaxed_params)
        target_atoms = config.get("target_atoms")
        relaxed_atoms = None if target_atoms is None else target_atoms.copy()
        return RelaxationComputeResult(
            final_energy=energy,
            n_steps=0,
            relaxed_params=relaxed_params,
            summary=summary,
            artifact_payloads=[
                {"role": "relaxation_summary", **summary, "target": target_uid}
            ],
            relaxed_atoms=relaxed_atoms,
            converged=True,
            max_force=0.0,
            max_optimizer_residual=0.0,
            optimizer_reported_converged=True,
        )


class RealRelaxationBackend:
    """ASE BFGS backend for authoritative persisted interface targets.

    Fixed-cell mode optimizes Cartesian atomic coordinates.  Interface-cell
    mode uses ``FrechetCellFilter`` with the strain mask ``xx, yy, xy`` so the
    interface-normal vector and boundary-vacuum direction remain fixed.
    """

    name = "real"
    requires_target_atoms = True

    def identity(self, *, targets: Any, uow: Any) -> dict[str, Any]:
        from ..followups.calculator_resolution import (
            require_calculator_from_prototype,
        )

        prototype_uids = sorted(
            {str(target["prototype_uid_full"]) for target in targets}
        )
        calculators: dict[str, Any] = {}
        with uow as entered:
            for prototype_uid in prototype_uids:
                spec = require_calculator_from_prototype(
                    entered,
                    prototype_uid,
                )
                calculators[prototype_uid] = spec.to_dict()
        return {
            "name": self.name,
            "algorithm": "ase_bfgs_interface_relaxation_v2",
            "scientific_authority": "calculator_backed",
            "optimizer": PERSISTED_OPTIMIZER,
            "cell_filter": PERSISTED_CELL_FILTER,
            "cell_factor_mode": PERSISTED_CELL_FACTOR_MODE,
            "interface_cell_mask": list(INTERFACE_CELL_MASK),
            "software_versions": {
                "ase": _installed_distribution_version("ase"),
                "numpy": _installed_distribution_version("numpy"),
                "scipy": _installed_distribution_version("scipy"),
            },
            "calculator_specs": calculators,
        }

    @staticmethod
    def _atoms_snapshot(atoms: Any) -> dict[str, Any]:
        return {
            "positions": atoms.get_positions(),
            "cell": atoms.get_cell(),
            "numbers": atoms.get_atomic_numbers(),
            "pbc": atoms.get_pbc(),
        }

    @staticmethod
    def _decode_target_atoms(value: Any, *, target_uid: str) -> Any:
        atoms = value
        if atoms is not None and isinstance(atoms, dict):
            try:
                from calm.structure.payloads import dict_to_atoms

                atoms = dict_to_atoms(atoms)
            except CALMOptionalDependencyError:
                raise
            except Exception as exc:
                raise RuntimeError(
                    "Could not decode persisted atoms for interface "
                    f"{target_uid}: {exc}"
                ) from exc
        return atoms

    @staticmethod
    def _construct_target(
        *,
        atoms: Any,
        relax_cell: bool,
    ) -> tuple[Any, float | None]:
        if not relax_cell:
            return atoms, None
        try:
            from ase.filters import FrechetCellFilter
        except ImportError as exc:
            raise OptionalDependencyError(
                "Interface cell relaxation requires ASE FrechetCellFilter. "
                "Install or upgrade `ase`."
            ) from exc
        factor = float(len(atoms))
        if factor <= 0.0:
            raise RuntimeError("Interface relaxation requires at least one atom.")
        target = FrechetCellFilter(
            atoms,
            mask=list(INTERFACE_CELL_MASK),
            exp_cell_factor=factor,
        )
        return target, factor

    def compute(  # noqa: C901
        self,
        *,
        run_uid: str,
        prototype_uid: str,
        target_uid: str,
        config: Mapping[str, Any],
        uow: Any,
    ) -> RelaxationComputeResult:
        del run_uid
        controls = canonical_relaxation_controls(
            protocol=config.get("protocol", "ionic_positions_v1"),
            convergence=config.get("convergence"),
            max_steps=config.get("max_steps", 500),
            relax_cell=config.get("relax_cell", False),
        )
        if str(config.get("target_kind") or "") != "interface":
            raise RuntimeError(
                "Authoritative relaxation requires a persisted atomistic interface "
                "target; implicit prototype reconstruction is not supported."
            )
        import numpy as np

        try:
            from ase.optimize import BFGS
        except ImportError as exc:  # pragma: no cover - optional backend
            raise OptionalDependencyError(
                "Real relaxation requires ASE BFGS. Install or upgrade `ase`."
            ) from exc
        from calm.calculators.runtime import construct_calculator
        from ..followups.calculator_resolution import (
            require_calculator_from_prototype,
        )

        if uow is None:
            raise RuntimeError(
                "RealRelaxationBackend requires a UnitOfWork to resolve "
                "calculator provenance."
            )

        with uow:
            calc_spec = require_calculator_from_prototype(uow, prototype_uid)

        atoms = self._decode_target_atoms(
            config.get("target_atoms"),
            target_uid=target_uid,
        )
        if atoms is None:
            raise RuntimeError(
                "No persisted atomistic payload is available for interface target "
                f"{target_uid}."
            )

        try:
            atoms = atoms.copy()
            initial = self._atoms_snapshot(atoms)
            deformation_before = validate_interface_deformation_provenance(atoms)
            source_deformation_before = deformation_before.get(
                INTERFACE_DEFORMATION_ACCOUNTING_INFO_KEY
            )
        except Exception as exc:
            raise CalculatorExecutionError(
                "Failed to detach or inspect the relaxation target structure: "
                f"{type(exc).__name__}: {exc}"
            ) from exc
        calculator = construct_calculator(calc_spec, quiet=True)
        try:
            atoms.calc = calculator
        except Exception as exc:
            raise CalculatorExecutionError(
                "Could not attach the requested calculator to the relaxation "
                f"target: {type(exc).__name__}: {exc}"
            ) from exc

        try:  # pragma: no cover - optional backend
            target, cell_factor = self._construct_target(
                atoms=atoms,
                relax_cell=controls.relax_cell,
            )
            optimizer = BFGS(target, logfile=None)
            optimizer_converged = bool(
                optimizer.run(
                    fmax=controls.force_tolerance_eV_per_A,
                    steps=controls.max_steps,
                )
            )
            final_energy = float(atoms.get_potential_energy())
            atomic_forces = np.asarray(atoms.get_forces(), dtype=float)
            generalized_forces = (
                np.asarray(target.get_forces(), dtype=float)
                if controls.relax_cell
                else atomic_forces
            )
            final = self._atoms_snapshot(atoms)
            cell_mode = "interface_in_plane" if controls.relax_cell else "fixed"
            transition = validate_relaxed_structure_transition(
                initial_positions=initial["positions"],
                final_positions=final["positions"],
                initial_cell=initial["cell"],
                final_cell=final["cell"],
                initial_numbers=initial["numbers"],
                final_numbers=final["numbers"],
                initial_pbc=initial["pbc"],
                final_pbc=final["pbc"],
                cell_mode=cell_mode,
            )
            relaxation_deformation = record_interface_relaxation_deformation(
                atoms,
                initial_cell=initial["cell"],
                final_cell=final["cell"],
                cell_mode=cell_mode,
            )
            deformation_after = validate_interface_deformation_provenance(atoms)
            if source_deformation_before is not None and (
                deformation_after.get(INTERFACE_DEFORMATION_ACCOUNTING_INFO_KEY)
                != source_deformation_before
            ):
                raise RuntimeError(
                    "Structural relaxation changed the authoritative source slab "
                    "deformation accounting."
                )
            max_atomic_force = max_vector_norm(
                "Relaxation atomic forces",
                atomic_forces,
                rows=len(atoms),
            )
            max_optimizer_residual = max_vector_norm(
                "Relaxation generalized forces",
                generalized_forces,
            )
            n_steps = int(getattr(optimizer, "nsteps", controls.max_steps))
            certificate = validate_relaxation_result(
                final_energy_eV=final_energy,
                n_steps=n_steps,
                max_steps=controls.max_steps,
                converged=optimizer_converged,
                max_atomic_force_eV_per_A=max_atomic_force,
                max_optimizer_residual=max_optimizer_residual,
                force_tolerance_eV_per_A=controls.force_tolerance_eV_per_A,
            )
        except CalculatorError:
            raise
        except Exception as exc:
            raise CalculatorExecutionError(
                f"ASE relaxation failed: {type(exc).__name__}: {exc}"
            ) from exc

        summary = {
            "relaxation_backend": self.name,
            "scientific_authority": "calculator_backed",
            "final_energy_eV": certificate["final_energy_eV"],
            "n_steps": certificate["n_steps"],
            "max_steps": certificate["max_steps"],
            "fmax_eV_per_A": certificate["force_tolerance_eV_per_A"],
            "max_force_eV_per_A": certificate["max_atomic_force_eV_per_A"],
            "max_optimizer_residual": certificate["max_optimizer_residual"],
            "relax_cell": controls.relax_cell,
            "protocol": controls.protocol,
            "optimizer": controls.optimizer,
            "cell_filter": controls.cell_filter,
            "cell_factor_mode": (
                PERSISTED_CELL_FACTOR_MODE if controls.relax_cell else None
            ),
            "cell_factor": cell_factor,
            "cell_mask": (
                list(controls.cell_mask) if controls.cell_mask is not None else None
            ),
            "optimizer_reported_converged": certificate["optimizer_reported_converged"],
            "residual_satisfied": certificate["residual_satisfied"],
            "converged": certificate["converged"],
            "termination_reason": certificate["termination_reason"],
            "deformation_accounting": relaxation_deformation,
            **transition,
        }
        return RelaxationComputeResult(
            final_energy=certificate["final_energy_eV"],
            n_steps=certificate["n_steps"],
            relaxed_params=dict(summary),
            summary=summary,
            artifact_payloads=[{"role": "relaxation_summary", **summary}],
            relaxed_atoms=atoms,
            converged=certificate["converged"],
            max_force=certificate["max_atomic_force_eV_per_A"],
            max_optimizer_residual=certificate["max_optimizer_residual"],
            optimizer_reported_converged=certificate["optimizer_reported_converged"],
        )


def make_relaxation_backend(name: str):
    """Return one built-in relaxation backend by canonical name."""

    normalized = (name or "real").strip().lower()
    if normalized in {"deterministic", "stub"}:
        return DeterministicRelaxationBackend()
    if normalized in {"real", "ase"}:
        return RealRelaxationBackend()
    raise ValueError(f"Unknown relaxation backend: {name!r}")
