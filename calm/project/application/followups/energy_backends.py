from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, Mapping

from calm.project.domain.contracts.relaxed_reference import (
    RELAXED_SURFACE_REFERENCE_KINDS,
)
from calm.calculators.exceptions import (
    CalculatorError,
    CalculatorExecutionError,
)
from calm.exceptions import OptionalDependencyError


@dataclass
class EnergyComputeResult:
    energy: float
    n_steps: int
    summary: dict[str, Any]
    artifact_payloads: list[dict[str, Any]]
    relaxed_atoms: Any | None = None
    relaxation_summary: dict[str, Any] | None = None


class DeterministicEnergyBackend:
    """Deterministic energy backend for tests.

    Produces a pseudo-energy deterministically from inputs.
    """

    name = "deterministic"

    def identity(self, *, targets, uow=None) -> dict[str, Any]:
        del targets, uow
        return {
            "name": self.name,
            "algorithm": "sha256_pseudo_energy_v1",
            "scientific_authority": "synthetic_test_only",
        }

    def compute(
        self,
        *,
        run_uid: str,
        prototype_uid: str,
        target_uid: str,
        config: Mapping[str, Any],
        uow: Any | None = None,
    ) -> EnergyComputeResult:
        if config.get("reference_relaxation") is not None:
            raise RuntimeError(
                "The deterministic energy backend cannot create scientific "
                "relaxed isolated-surface references."
            )
        import hashlib

        mode = config.get("mode", "single_point")
        key = f"{run_uid}:{prototype_uid}:{target_uid}:{mode}"
        h = hashlib.sha256(key.encode("utf-8")).hexdigest()
        energy = (int(h[:8], 16) % 100000) / 1000.0
        n_steps = int(config.get("n_steps", 1))
        summary = {"energy": energy, "n_steps": n_steps}
        artifact_payloads = [{"summary": summary}]
        return EnergyComputeResult(
            energy=energy,
            n_steps=n_steps,
            summary=summary,
            artifact_payloads=artifact_payloads,
        )


def _load_real_energy_dependencies():
    """Load the optional calculator and interface-energy dependencies."""

    from calm.calculators.runtime import construct_calculator

    from ..followups.calculator_resolution import (
        require_calculator_from_prototype,
    )
    from ..followups.interface_energy import (
        build_interface_from_prototype_with_strain,
        compute_interface_energy,
    )

    return (
        construct_calculator,
        require_calculator_from_prototype,
        build_interface_from_prototype_with_strain,
        compute_interface_energy,
    )


def _resolve_real_calculator_spec(
    *,
    uow: Any,
    prototype_uid: str,
    resolver: Any,
) -> Any:
    """Resolve the authoritative calculator specification for one prototype."""

    with uow:
        return resolver(uow, prototype_uid)


def _real_target_atoms(
    *,
    config: Mapping[str, Any],
    uow: Any,
    prototype_uid: str,
    builder: Any,
) -> Any:
    """Return a detached target structure or rebuild the legacy default target."""

    target_atoms = config.get("target_atoms")
    if target_atoms is not None:
        try:
            return target_atoms.copy()
        except Exception as exc:
            raise CalculatorExecutionError(
                "Could not detach target atoms before calculator execution: "
                f"{type(exc).__name__}: {exc}"
            ) from exc
    try:
        return builder(
            uow,
            prototype_uid,
            alpha=0.5,
            translation_frac=(0.0, 0.0),
            z_padding=1.5,
        )
    except (CalculatorError, OptionalDependencyError):
        raise
    except Exception as exc:
        raise RuntimeError(f"Failed to obtain target interface atoms: {exc}") from exc


def _attach_real_calculator(
    *,
    atoms: Any,
    calc_spec: Any,
    maker: Any,
) -> Any:
    """Construct and attach the requested calculator."""

    calc = maker(calc_spec, quiet=True)
    try:
        atoms.calc = calc
    except Exception as exc:
        raise CalculatorExecutionError(
            "Could not attach the requested calculator to target atoms: "
            f"{type(exc).__name__}: {exc}"
        ) from exc
    return calc


def _compute_real_single_point(
    *,
    atoms: Any,
    calc_spec: Any,
    calc: Any,
    evaluator: Any,
) -> EnergyComputeResult:
    """Evaluate one non-relaxed calculator-backed energy."""

    try:
        final_energy = evaluator(
            atoms,
            calc_spec,
            relax=False,
            calc=calc,
        )
        energy_val = float(final_energy)
    except (CalculatorError, OptionalDependencyError):
        raise
    except Exception as exc:
        raise CalculatorExecutionError(
            f"Real energy computation failed: {type(exc).__name__}: {exc}"
        ) from exc
    if not isfinite(energy_val):
        raise CalculatorExecutionError(
            "Real energy computation returned a non-finite energy."
        )
    summary = {"energy": energy_val}
    return EnergyComputeResult(
        energy=energy_val,
        n_steps=1,
        summary=summary,
        artifact_payloads=[summary],
    )


class RealEnergyBackend:
    """Real energy backend that uses calculator helpers to compute energies.

    This class lazily imports heavy dependencies and raises informative
    RuntimeError when optional deps are missing.
    """

    name = "real"

    def identity(self, *, targets, uow) -> dict[str, Any]:
        from ..followups.calculator_resolution import (
            require_calculator_from_prototype,
        )

        prototype_uids = sorted(
            {str(target["prototype_uid_full"]) for target in targets}
        )
        calculators: dict[str, Any] = {}
        with uow as entered:
            for prototype_uid in prototype_uids:
                spec = require_calculator_from_prototype(entered, prototype_uid)
                calculators[prototype_uid] = spec.to_dict()
        result = {
            "name": self.name,
            "scientific_authority": "calculator_backed",
            "calculator_specs": calculators,
        }
        reference_kinds = {
            str(target.get("reference_kind") or "") for target in targets
        }
        if reference_kinds.intersection(RELAXED_SURFACE_REFERENCE_KINDS):
            from .relaxation_backends import _installed_distribution_version

            result["reference_relaxation_engine"] = {
                "algorithm": ("ase_bfgs_fixed_cell_surface_relaxation_v1"),
                "optimizer": "ASE.BFGS",
                "software_versions": {
                    "ase": _installed_distribution_version("ase"),
                    "numpy": _installed_distribution_version("numpy"),
                    "scipy": _installed_distribution_version("scipy"),
                },
            }
        return result

    @staticmethod
    def _compute_relaxed_reference(
        atoms: Any,
        relaxation_settings: Mapping[str, Any],
    ) -> EnergyComputeResult:
        """Relax one isolated surface in its fixed authoritative cell."""

        import numpy as np

        try:
            from ase.optimize import BFGS
        except ImportError as exc:
            raise OptionalDependencyError(
                "Relaxed surface references require ASE BFGS. Install or upgrade `ase`."
            ) from exc

        from calm.project.domain.contracts.relaxation import (
            max_vector_norm,
            validate_relaxation_result,
            validate_relaxed_structure_transition,
        )
        from calm.project.domain.contracts.relaxed_reference import (
            RELAXED_SURFACE_PROTOCOL,
            canonical_surface_relaxation_settings,
        )

        controls = canonical_surface_relaxation_settings(relaxation_settings)
        initial_positions = atoms.get_positions().copy()
        initial_cell = atoms.get_cell().copy()
        initial_numbers = atoms.get_atomic_numbers().copy()
        initial_pbc = atoms.get_pbc().copy()
        optimizer = BFGS(atoms, logfile=None)
        optimizer_converged = bool(
            optimizer.run(
                fmax=controls["fmax"],
                steps=controls["steps"],
            )
        )
        final_energy = float(atoms.get_potential_energy())
        forces = np.asarray(atoms.get_forces(), dtype=float)
        max_force = max_vector_norm(
            "Relaxed surface atomic forces",
            forces,
            rows=len(atoms),
        )
        n_steps = int(getattr(optimizer, "nsteps", controls["steps"]))
        certificate = validate_relaxation_result(
            final_energy_eV=final_energy,
            n_steps=n_steps,
            max_steps=controls["steps"],
            converged=optimizer_converged,
            max_atomic_force_eV_per_A=max_force,
            max_optimizer_residual=max_force,
            force_tolerance_eV_per_A=controls["fmax"],
        )
        transition = validate_relaxed_structure_transition(
            initial_positions=initial_positions,
            final_positions=atoms.get_positions(),
            initial_cell=initial_cell,
            final_cell=atoms.get_cell(),
            initial_numbers=initial_numbers,
            final_numbers=atoms.get_atomic_numbers(),
            initial_pbc=initial_pbc,
            final_pbc=atoms.get_pbc(),
            cell_mode="fixed",
        )
        relaxation_summary = {
            "protocol": RELAXED_SURFACE_PROTOCOL,
            "scientific_authority": "calculator_backed",
            "optimizer": "ASE.BFGS",
            "fmax": controls["fmax"],
            "steps": controls["steps"],
            "n_steps": certificate["n_steps"],
            "max_force_eV_per_A": certificate["max_atomic_force_eV_per_A"],
            "relax_cell": False,
            "converged": certificate["converged"],
            "termination_reason": certificate["termination_reason"],
            **transition,
        }
        summary = {
            "energy": certificate["final_energy_eV"],
            "relaxation": relaxation_summary,
        }
        from calm.structure.payloads import atoms_to_dict

        return EnergyComputeResult(
            energy=certificate["final_energy_eV"],
            n_steps=certificate["n_steps"],
            summary=summary,
            artifact_payloads=[
                {"role": "relaxed_surface_summary", **summary},
                {
                    "role": "relaxed_surface_atoms",
                    "atoms": atoms_to_dict(atoms),
                },
            ],
            relaxed_atoms=atoms,
            relaxation_summary=relaxation_summary,
        )

    def compute(
        self,
        *,
        run_uid: str,
        prototype_uid: str,
        target_uid: str,
        config: Mapping[str, Any],
        uow: Any,
    ) -> EnergyComputeResult:
        del run_uid, target_uid
        if uow is None:
            raise RuntimeError("RealEnergyBackend requires a UnitOfWork instance (uow)")

        (
            construct_calculator,
            require_calculator_from_prototype,
            build_interface_from_prototype_with_strain,
            compute_interface_energy,
        ) = _load_real_energy_dependencies()
        calc_spec = _resolve_real_calculator_spec(
            uow=uow,
            prototype_uid=prototype_uid,
            resolver=require_calculator_from_prototype,
        )
        atoms = _real_target_atoms(
            config=config,
            uow=uow,
            prototype_uid=prototype_uid,
            builder=build_interface_from_prototype_with_strain,
        )
        calc = _attach_real_calculator(
            atoms=atoms,
            calc_spec=calc_spec,
            maker=construct_calculator,
        )

        relaxation_settings = config.get("reference_relaxation")
        if relaxation_settings is not None:
            try:
                return self._compute_relaxed_reference(
                    atoms,
                    relaxation_settings,
                )
            except (CalculatorError, OptionalDependencyError):
                raise
            except Exception as exc:
                raise CalculatorExecutionError(
                    "Real relaxed-reference computation failed: "
                    f"{type(exc).__name__}: {exc}"
                ) from exc

        return _compute_real_single_point(
            atoms=atoms,
            calc_spec=calc_spec,
            calc=calc,
            evaluator=compute_interface_energy,
        )


def make_energy_backend(name: str):
    n = (name or "deterministic").strip().lower()
    if n in ("deterministic", "stub"):
        b = DeterministicEnergyBackend()
        setattr(b, "name", "deterministic")
        return b
    if n in ("real", "ase"):
        b = RealEnergyBackend()
        setattr(b, "name", "real")
        return b
    raise ValueError(f"Unknown energy backend: {name!r}")
