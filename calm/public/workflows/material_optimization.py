"""Internal composition owner for public bulk-material optimization."""

from __future__ import annotations

from contextlib import nullcontext
from typing import Any


class ProjectMaterialOptimizationService:
    """Compose one calculator-backed bulk optimization and persistence workflow."""

    def __init__(self, *, project: Any, saver: Any):
        self._project = project
        self._saver = saver

    @staticmethod
    def _label(value: Any) -> str:
        if value is None:
            return "<none>"
        return str(
            getattr(value, "label", None)
            or getattr(value, "name", None)
            or getattr(value, "id_short", None)
            or type(value).__name__
        )

    @staticmethod
    def _calculator_from_inputs(
        *,
        potential: Any | None = None,
        calculator: Any | None = None,
    ) -> Any:
        if potential is not None and calculator is not None:
            raise TypeError(
                "Provide exactly one of potential= or calculator= for bulk "
                "optimization."
            )
        if potential is not None:
            from calm.public.inputs.potentials import Potential

            if not isinstance(potential, Potential):
                raise TypeError("potential must be a calm.Potential instance.")
            return potential.calculator()
        if calculator is None:
            raise ValueError(
                "Bulk optimization requires potential=... or calculator=...."
            )
        return calculator

    @staticmethod
    def _potential_spec(potential: Any | None):
        if potential is None:
            return None
        from calm.calculators.spec import CalculatorSpec
        from calm.public.inputs.potentials import Potential

        if not isinstance(potential, Potential):
            raise TypeError("potential must be a calm.Potential instance.")
        raw = potential.to_spec()
        if isinstance(raw, CalculatorSpec):
            return raw
        return CalculatorSpec.from_dict(raw)

    @staticmethod
    def _optimize_structure(
        material: Any,
        *,
        potential: Any | None = None,
        calculator: Any | None = None,
        fmax: float,
        steps: int,
        relax_cell: bool,
        optimizer: str,
    ):
        """Return one converged optimized material without persisting it."""
        import numpy as np

        from calm.project.domain.contracts.relaxation import (
            canonical_optimizer_name,
            exact_bool,
            exact_positive_integer,
            finite_positive_real,
            max_vector_norm,
            validate_relaxation_result,
            validate_relaxed_structure_transition,
        )
        from calm.calculators.exceptions import (
            CalculatorError,
            CalculatorExecutionError,
        )
        from calm.calculators.identity import get_calculator_uid
        from calm.exceptions import OptionalDependencyError
        from calm.public.inputs.materials import Material

        if not isinstance(material, Material):
            raise TypeError(
                "material must be a calm.Material or a persisted material selector."
            )

        force_tolerance = finite_positive_real("fmax", fmax)
        step_limit = exact_positive_integer("steps", steps)
        cell_relax = exact_bool("relax_cell", relax_cell)
        optimizer_name = canonical_optimizer_name(optimizer)
        calc = ProjectMaterialOptimizationService._calculator_from_inputs(
            potential=potential,
            calculator=calculator,
        )

        source_atoms = material.to_ase()
        if source_atoms is None or not hasattr(source_atoms, "copy"):
            raise TypeError("Bulk optimization requires an Atoms-like structure.")

        cell_filter_type = None
        if cell_relax:
            try:
                from ase.filters import FrechetCellFilter
            except ImportError as exc:
                raise OptionalDependencyError(
                    "Bulk cell relaxation requires ASE FrechetCellFilter. "
                    "Install or upgrade `ase`."
                ) from exc
            cell_filter_type = FrechetCellFilter

        try:
            if optimizer_name == "BFGS":
                from ase.optimize import BFGS as Optimizer
            elif optimizer_name == "LBFGS":
                from ase.optimize import LBFGS as Optimizer
            else:
                from ase.optimize import FIRE as Optimizer
        except ImportError as exc:
            raise OptionalDependencyError(
                f"Bulk optimization requires ASE {optimizer_name}. "
                "Install or upgrade `ase`."
            ) from exc

        quiet_context = nullcontext()
        if potential is not None and potential.quiet:
            from calm.calculators.quiet import suppress_mlip_output

            quiet_context = suppress_mlip_output()

        try:
            atoms = source_atoms.copy()
            calculator_identity = {
                "class": f"{type(calc).__module__}.{type(calc).__qualname__}",
                "uid": get_calculator_uid(calc),
            }
            initial = {
                "positions": atoms.get_positions(),
                "cell": atoms.get_cell(),
                "numbers": atoms.get_atomic_numbers(),
                "pbc": atoms.get_pbc(),
            }
            with quiet_context:
                atoms.calc = calc
                target: Any = atoms
                cell_filter = None
                cell_factor = None
                if cell_relax:
                    cell_factor = float(len(atoms))
                    if cell_factor <= 0.0:
                        raise ValueError(
                            "Bulk optimization requires at least one atom."
                        )
                    target = cell_filter_type(
                        atoms,
                        exp_cell_factor=cell_factor,
                    )
                    cell_filter = "FrechetCellFilter"

                dynamics = Optimizer(target, logfile=None)
                optimizer_converged = bool(
                    dynamics.run(fmax=force_tolerance, steps=step_limit)
                )
                final_energy = float(atoms.get_potential_energy())
                atomic_forces = np.asarray(atoms.get_forces(), dtype=float)
                generalized_forces = (
                    np.asarray(target.get_forces(), dtype=float)
                    if cell_relax
                    else atomic_forces
                )
                final = {
                    "positions": atoms.get_positions(),
                    "cell": atoms.get_cell(),
                    "numbers": atoms.get_atomic_numbers(),
                    "pbc": atoms.get_pbc(),
                }
                transition = validate_relaxed_structure_transition(
                    initial_positions=initial["positions"],
                    final_positions=final["positions"],
                    initial_cell=initial["cell"],
                    final_cell=final["cell"],
                    initial_numbers=initial["numbers"],
                    final_numbers=final["numbers"],
                    initial_pbc=initial["pbc"],
                    final_pbc=final["pbc"],
                    cell_mode="full" if cell_relax else "fixed",
                )
                max_atomic_force = max_vector_norm(
                    "Bulk relaxation atomic forces",
                    atomic_forces,
                    rows=len(atoms),
                )
                max_optimizer_residual = max_vector_norm(
                    "Bulk relaxation generalized forces",
                    generalized_forces,
                )
                certificate = validate_relaxation_result(
                    final_energy_eV=final_energy,
                    n_steps=int(getattr(dynamics, "nsteps", step_limit)),
                    max_steps=step_limit,
                    converged=optimizer_converged,
                    max_atomic_force_eV_per_A=max_atomic_force,
                    max_optimizer_residual=max_optimizer_residual,
                    force_tolerance_eV_per_A=force_tolerance,
                )
        except (CalculatorError, OptionalDependencyError):
            raise
        except Exception as exc:
            raise CalculatorExecutionError(
                "Bulk optimization failed during calculator-backed execution: "
                f"{type(exc).__name__}: {exc}"
            ) from exc

        if not certificate["converged"]:
            raise CalculatorExecutionError(
                "Bulk optimization exhausted its step budget without satisfying "
                "the optimizer-residual convergence criterion."
            )

        metadata = dict(material.metadata)
        metadata.update(
            {
                "optimizer": optimizer_name,
                "cell_filter": cell_filter,
                "cell_factor_mode": "n_atoms" if cell_relax else None,
                "cell_factor": cell_factor,
                "fmax": force_tolerance,
                "steps": step_limit,
                "relax_cell": cell_relax,
                "potential": getattr(potential, "name", None),
                "calculator_identity": calculator_identity,
                "convergence_certificate": certificate,
                "geometry_transition": transition,
            }
        )
        formula = (
            atoms.get_chemical_formula()
            if hasattr(atoms, "get_chemical_formula")
            else material.formula
        )
        return Material(
            name=material.name,
            label=material.label,
            atoms=atoms,
            formula=formula,
            state="optimized_bulk",
            metadata=metadata,
        )

    def optimize_material(
        self,
        material: Any,
        *,
        potential: Any | None = None,
        calculator: Any | None = None,
        name: str | None = None,
        reporter: Any | None = None,
        fmax: float = 0.03,
        steps: int = 500,
        relax_cell: bool = True,
        optimizer: str = "BFGS",
    ):
        """Optimize and persist one material through the sole public workflow."""
        from calm.public.presentation.reporting import ensure_console_reporter

        if isinstance(material, str):
            material = self._project.material(material)

        rep = ensure_console_reporter(reporter)
        source_label = self._label(material)
        destination_label = name or source_label
        spec = self._potential_spec(potential)
        with rep.stage(f"Optimize material: {source_label} -> {destination_label}"):
            optimized = self._optimize_structure(
                material,
                potential=potential,
                calculator=calculator,
                fmax=fmax,
                steps=steps,
                relax_cell=relax_cell,
                optimizer=optimizer,
            )

        if spec is not None:
            setattr(optimized, "optimized_with", spec)
            from calm.public.inputs.project_config import configure

            configure(
                self._project,
                mlip=spec.family,
                calculator=spec.to_dict(),
                defaults=None,
            )

        saved = self._saver.persist_material(
            optimized,
            name=name,
            reporter=rep,
        )
        saved_id = getattr(saved, "id_short", None) or ""
        rep.info(f"Saved optimized material: {destination_label} ({saved_id})")
        return saved
