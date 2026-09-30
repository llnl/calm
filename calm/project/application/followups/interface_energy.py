"""Interface energy computation for followups.

Builds interface structures and computes energies using calculators.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

from calm.calculators.exceptions import (
    CalculatorError,
    CalculatorExecutionError,
    OptionalDependencyError,
)
from calm.calculators.runtime import construct_calculator
from calm.calculators.spec import CalculatorSpec
from calm.math2d._core import det2

from ...ports.uow import UnitOfWork
from ..interface_prototype_payload import load_interface_prototype

if TYPE_CHECKING:
    from ase import Atoms

    from calm.interface.model import InterfacePrototype


def _exact_integer_matrix_2d(name: str, value: Any) -> np.ndarray:
    """Return an exact finite integer 2x2 matrix without truncation."""
    array = np.asarray(value)
    if array.shape != (2, 2):
        raise ValueError(f"{name} must have shape (2, 2); got {array.shape}.")
    if array.dtype.kind in {"i", "u"}:
        return array.astype(int, copy=True)
    try:
        floating = np.asarray(value, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must contain exact integers.") from exc
    rounded = np.rint(floating)
    if not np.all(np.isfinite(floating)) or not np.array_equal(floating, rounded):
        raise ValueError(f"{name} must contain exact finite integers.")
    return rounded.astype(int)


def _orthogonal_gauge_3d(name: str, rotation_2d: Any) -> np.ndarray:
    """Embed and validate a persisted in-plane orthogonal gauge."""
    rotation = np.asarray(rotation_2d, dtype=float)
    if rotation.shape != (2, 2) or not np.all(np.isfinite(rotation)):
        raise ValueError(f"{name} must be a finite 2x2 matrix.")
    if not np.allclose(rotation.T @ rotation, np.eye(2), atol=1e-10, rtol=1e-10):
        raise ValueError(f"{name} must be orthogonal.")
    determinant = float(np.linalg.det(rotation))
    if not np.isclose(abs(determinant), 1.0, atol=1e-10, rtol=1e-10):
        raise ValueError(f"{name} must have determinant +1 or -1.")
    out = np.eye(3, dtype=float)
    out[:2, :2] = rotation
    return out


def _prototype_build_components(
    prototype: InterfacePrototype,
) -> tuple[Any, Any, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return build inputs from one fully validated persisted prototype."""

    slab_a = getattr(prototype.slab_a, "atoms", None)
    slab_b = getattr(prototype.slab_b, "atoms", None)
    if slab_a is None or slab_b is None:
        raise ValueError("Persisted prototype slab atoms are not available")

    return (
        slab_a,
        slab_b,
        prototype.supercell_a.N_tot,
        prototype.supercell_b.N_tot,
        prototype.supercell_a.R_sup,
        prototype.supercell_b.R_sup,
    )


def _prepare_loaded_interface_prototype(
    prototype: InterfacePrototype,
    *,
    alpha: float,
    z_padding: float,
    vacuum_padding: float | None,
):
    """Prepare one fully validated prototype for repeated translations."""

    slab_a, slab_b, U_A, U_B, R_A, R_B = _prototype_build_components(prototype)
    return _prepare_simple_interface(
        slab_a,
        slab_b,
        U_A,
        U_B,
        alpha,
        z_padding,
        R_A=R_A,
        R_B=R_B,
        vacuum_padding=vacuum_padding,
    )


def _build_loaded_interface_prototype(
    prototype: InterfacePrototype,
    *,
    alpha: float,
    translation_frac: tuple[float, float],
    z_padding: float,
    vacuum_padding: float | None,
):
    """Build one translated interface from a validated prototype."""

    slab_a, slab_b, U_A, U_B, R_A, R_B = _prototype_build_components(prototype)
    return _build_simple_interface(
        slab_a,
        slab_b,
        U_A,
        U_B,
        alpha,
        translation_frac,
        z_padding,
        R_A=R_A,
        R_B=R_B,
        vacuum_padding=vacuum_padding,
    )


def _strain_partition_geometry(
    prototype: InterfacePrototype,
    *,
    alpha: float,
):
    """Return geometric diagnostics from the exact prototype build state."""

    slab_a, slab_b, U_A, U_B, R_A, R_B = _prototype_build_components(prototype)
    _, _, _, _, partition = _simple_interface_partition(
        slab_a,
        slab_b,
        U_A,
        U_B,
        alpha=float(alpha),
        R_A=R_A,
        R_B=R_B,
    )
    return partition


def prepare_interface_from_prototype_with_strain(
    uow: UnitOfWork,
    prototype_uid_full: str,
    alpha: float,
    z_padding: float = 1.5,
    vacuum_padding: float | None = None,
):
    """Prepare fixed interface geometry for repeated registry translations."""

    prototype = load_interface_prototype(uow, prototype_uid_full)
    return _prepare_loaded_interface_prototype(
        prototype,
        alpha=alpha,
        z_padding=z_padding,
        vacuum_padding=vacuum_padding,
    )


def build_interface_from_prototype_with_strain(
    uow: UnitOfWork,
    prototype_uid_full: str,
    alpha: float,
    translation_frac: tuple[float, float] = (0.0, 0.0),
    z_padding: float = 1.5,
    vacuum_padding: float | None = None,
) -> Atoms:
    """Build one interface from the exact persisted prototype state."""

    prototype = load_interface_prototype(uow, prototype_uid_full)
    return _build_loaded_interface_prototype(
        prototype,
        alpha=alpha,
        translation_frac=translation_frac,
        z_padding=z_padding,
        vacuum_padding=vacuum_padding,
    )


def _simple_interface_partition(
    slab_a: Atoms,
    slab_b: Atoms,
    U_A: np.ndarray | None = None,
    U_B: np.ndarray | None = None,
    alpha: float = 0.0,
    *,
    R_A: np.ndarray | None = None,
    R_B: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, Any]:
    """Return the exact supercell, gauge, and geodesic partition state."""

    from calm.interface.building._kernel import _embed_2x2_in_3x3
    from calm.interface.refinement.partition import strain_partition_inplane

    U_A2 = np.eye(2, dtype=int) if U_A is None else _exact_integer_matrix_2d("U_A", U_A)
    U_B2 = np.eye(2, dtype=int) if U_B is None else _exact_integer_matrix_2d("U_B", U_B)
    R_A3 = _orthogonal_gauge_3d("R_A", np.eye(2, dtype=float) if R_A is None else R_A)
    R_B3 = _orthogonal_gauge_3d("R_B", np.eye(2, dtype=float) if R_B is None else R_B)
    P_A = _embed_2x2_in_3x3(U_A2, dtype="int")
    P_B = _embed_2x2_in_3x3(U_B2, dtype="int")

    cell_a_col = np.asarray(slab_a.cell, dtype=float).T
    cell_b_col = np.asarray(slab_b.cell, dtype=float).T
    basis_a = (R_A3 @ cell_a_col @ P_A)[:2, :2]
    basis_b = (R_B3 @ cell_b_col @ P_B)[:2, :2]
    partition = strain_partition_inplane(basis_a, basis_b, alpha=float(alpha))
    return P_A, P_B, R_A3, R_B3, partition


def _prepare_simple_interface(
    slab_a: Atoms,
    slab_b: Atoms,
    U_A: np.ndarray | None = None,
    U_B: np.ndarray | None = None,
    alpha: float = 0.0,
    z_padding: float = 1.5,
    *,
    R_A: np.ndarray | None = None,
    R_B: np.ndarray | None = None,
    vacuum_padding: float | None = None,
):
    """Prepare invariant supercell, gauge, strain, and stacking geometry."""

    from calm.interface.building._kernel import (
        _embed_2x2_in_3x3,
        prepare_interface_atoms,
    )

    P_A, P_B, R_A3, R_B3, partition = _simple_interface_partition(
        slab_a,
        slab_b,
        U_A,
        U_B,
        alpha,
        R_A=R_A,
        R_B=R_B,
    )
    F_A3 = _embed_2x2_in_3x3(partition.F_A, dtype="float")
    F_B3 = _embed_2x2_in_3x3(partition.F_B, dtype="float")

    return prepare_interface_atoms(
        slab_A_atoms=slab_a,
        slab_B_atoms=slab_b,
        N_A3=P_A,
        N_B3=P_B,
        R_A3=R_A3,
        R_B3=R_B3,
        F_A=F_A3,
        F_B=F_B3,
        z_padding=z_padding,
        vacuum_padding=vacuum_padding,
    )


def _build_simple_interface(
    slab_a: Atoms,
    slab_b: Atoms,
    U_A: np.ndarray | None = None,
    U_B: np.ndarray | None = None,
    alpha: float = 0.0,
    translation_frac: tuple[float, float] = (0.0, 0.0),
    z_padding: float = 1.5,
    *,
    R_A: np.ndarray | None = None,
    R_B: np.ndarray | None = None,
    vacuum_padding: float | None = None,
) -> Atoms:
    """Build one translated interface through the prepared geometry owner."""

    from calm.interface.building._kernel import build_prepared_interface_atoms

    prepared = _prepare_simple_interface(
        slab_a,
        slab_b,
        U_A,
        U_B,
        alpha,
        z_padding,
        R_A=R_A,
        R_B=R_B,
        vacuum_padding=vacuum_padding,
    )
    return build_prepared_interface_atoms(
        prepared,
        translation_frac=translation_frac,
    ).atoms


def compute_interface_energy(
    atoms: Atoms,
    calc_spec: CalculatorSpec,
    relax: bool = False,
    fmax: float = 0.05,
    calc=None,
) -> float:
    """Compute interface energy using calculator.

    Parameters
    ----------
    atoms : Atoms
        Interface structure
    calc_spec : CalculatorSpec
        Calculator specification
    relax : bool, optional
        Whether to relax structure before computing energy
    fmax : float, optional
        Force convergence criterion for relaxation (eV/Å)
    calc : Calculator, optional
        Pre-existing calculator instance to reuse. If None, creates new one.

    Returns
    -------
    float
        Total energy in eV

    Notes
    -----
    This function:
    1. Creates calculator from spec (or reuses provided instance)
    2. Attaches to atoms
    3. Optionally relaxes structure
    4. Returns total potential energy

    For efficiency, pass a pre-created calculator when computing multiple energies
    with the same calculator specification.
    """
    # Create calculator only if not provided
    if calc is None:
        # Use quiet suppression as a best-effort while creating MLIP calculators
        calc = construct_calculator(calc_spec, quiet=True)

    # Optionally relax
    optimizer_type = None
    if relax:
        try:
            from ase.optimize import BFGS as optimizer_type
        except ImportError as exc:
            raise OptionalDependencyError(
                "Interface relaxation requires ASE BFGS. Install or upgrade `ase`."
            ) from exc

    try:
        # Attach the exact requested calculator before any scientific work.
        atoms.calc = calc
        if optimizer_type is not None:
            optimizer = optimizer_type(atoms, logfile=None)
            optimizer.run(fmax=fmax)
        total_energy_eV = float(atoms.get_potential_energy())
    except CalculatorError:
        raise
    except Exception as exc:
        raise CalculatorExecutionError(
            f"Calculator-backed interface execution failed: {type(exc).__name__}: {exc}"
        ) from exc
    if not np.isfinite(total_energy_eV):
        raise CalculatorExecutionError(
            "Calculator returned a non-finite interface potential energy."
        )

    return total_energy_eV


class StrainedBulkReferenceUnavailableError(RuntimeError):
    """The persisted target lacks exact context for strained-bulk gamma."""


def _require_strained_bulk_reference_context(prototype: Any) -> None:
    """Require both prototype slabs to retain their parent bulk objects.

    Project-rehydrated slabs intentionally preserve exact finite slab geometry
    but do not currently reconstruct the scientific ``Bulk`` objects required
    to build strained reference cells. That known absence makes gamma
    unavailable; all other geometry and execution failures must propagate.
    """

    for side in ("a", "b"):
        slab = getattr(prototype, f"slab_{side}", None)
        if slab is None or getattr(slab, "bulk", None) is None:
            raise StrainedBulkReferenceUnavailableError(
                "Strained-bulk gamma requires side-"
                f"{side.upper()} parent-bulk context, which is unavailable on "
                "the persisted slab record."
            )


def _compute_strained_bulk_gamma(
    prototype: Any,
    *,
    alpha: float,
    translation_frac: tuple[float, float],
    z_padding: float,
    calculator: Any,
    energy_config: Any | None,
) -> Any:
    """Evaluate gamma only when exact strained-bulk context is available."""

    _require_strained_bulk_reference_context(prototype)

    from calm.interface.config import InterfaceBuildConfig, StrainModel
    from calm.interface.pipeline import (
        build_interface,
        compute_interfacial_energy,
        compute_strain_state,
    )

    strain = compute_strain_state(
        prototype,
        model=StrainModel(alpha=float(alpha)),
    )
    build_config = InterfaceBuildConfig(
        translation_frac=(
            float(translation_frac[0]),
            float(translation_frac[1]),
        ),
        z_padding=float(z_padding),
        vacuum_padding=float(z_padding),
    )
    interface = build_interface(prototype, strain, build=build_config)
    return compute_interfacial_energy(
        interface,
        calculator,
        config=energy_config,
    )


def compute_strain_scan_energy_point(
    uow: UnitOfWork,
    prototype_uid_full: str,
    alpha: float,
    calc_spec: CalculatorSpec,
    translation_frac: tuple[float, float] = (0.0, 0.0),
    z_padding: float = 1.5,
    calc=None,
    energy_config: Any | None = None,
) -> dict:
    """Compute rich energy point for a strain-scan alpha.

    Returns a dict containing both raw potential energy and reference-subtracted
    interfacial energy (gamma) along with area and provenance fields.
    """
    prototype = load_interface_prototype(uow, prototype_uid_full)
    atoms = _build_loaded_interface_prototype(
        prototype,
        alpha=alpha,
        translation_frac=translation_frac,
        z_padding=z_padding,
        vacuum_padding=None,
    )

    calc_local = calc
    if calc_local is None:
        calc_local = construct_calculator(calc_spec, quiet=True)

    partition = _strain_partition_geometry(
        prototype,
        alpha=float(alpha),
    )

    # Total potential energy (raw)
    potential_energy_eV = float(_compute_energy_with_calc(atoms, calc_local))

    # Area
    cell = atoms.get_cell()
    S_inplane = np.array([[cell[0, 0], cell[1, 0]], [cell[0, 1], cell[1, 1]]])
    area_A2 = abs(det2(S_inplane, mode="float"))
    if not np.isfinite(area_A2) or area_A2 <= 0.0:
        raise ValueError("Strain-scan interface area must be finite and positive.")
    partition_area_A2 = abs(det2(partition.X, mode="float"))
    if not np.isfinite(partition_area_A2) or partition_area_A2 <= 0.0:
        raise ValueError("Strain-partition target area must be finite and positive.")
    if not np.isclose(
        area_A2,
        partition_area_A2,
        rtol=1e-10,
        atol=1e-10,
    ):
        raise ValueError(
            "Built interface area does not match the geodesic target metric: "
            f"{area_A2!r} != {partition_area_A2!r}."
        )
    potential_energy_density = float(potential_energy_eV) / float(area_A2)

    # Compute gamma only when both persisted slabs retain exact parent-bulk
    # context. A known absence is represented as unavailable; unexpected
    # geometry, provenance, and calculator failures propagate unchanged.
    gamma_eV_per_A2 = float("nan")
    gamma_J_per_m2 = float("nan")
    mu_bulk_A = None
    mu_bulk_B = None
    n_fu_slab_A = None
    n_fu_slab_B = None

    try:
        energy_res = _compute_strained_bulk_gamma(
            prototype,
            alpha=float(alpha),
            translation_frac=translation_frac,
            z_padding=float(z_padding),
            calculator=calc_local,
            energy_config=energy_config,
        )
    except StrainedBulkReferenceUnavailableError:
        pass
    else:
        gamma_eV_per_A2 = float(energy_res.gamma_eV_per_A2)
        gamma_J_per_m2 = float(energy_res.gamma_J_per_m2)
        n_fu_slab_A = int(energy_res.n_fu_slab_A)
        n_fu_slab_B = int(energy_res.n_fu_slab_B)
        mu_bulk_A = float(getattr(energy_res, "mu_bulk_A_eV_per_fu", float("nan")))
        mu_bulk_B = float(getattr(energy_res, "mu_bulk_B_eV_per_fu", float("nan")))

    return {
        "alpha": float(alpha),
        "side_a_principal_log_strains": list(partition.side_a_principal_log_strains),
        "side_b_principal_log_strains": list(partition.side_b_principal_log_strains),
        "side_a_max_abs_principal_log_strain": float(
            partition.side_a_max_abs_principal_log_strain
        ),
        "side_b_max_abs_principal_log_strain": float(
            partition.side_b_max_abs_principal_log_strain
        ),
        "side_a_airm_distance": float(partition.side_a_airm_distance),
        "side_b_airm_distance": float(partition.side_b_airm_distance),
        "potential_energy_eV": float(potential_energy_eV),
        "area_A2": float(area_A2),
        "interface_area_A2": float(area_A2),
        "potential_energy_density_eV_per_A2": float(potential_energy_density),
        "gamma_eV_per_A2": float(gamma_eV_per_A2),
        "gamma_J_per_m2": float(gamma_J_per_m2),
        "n_fu_slab_A": n_fu_slab_A,
        "n_fu_slab_B": n_fu_slab_B,
        "mu_bulk_A_eV_per_fu": mu_bulk_A,
        "mu_bulk_B_eV_per_fu": mu_bulk_B,
        "energy_reference": "strained_bulk",
    }


def _compute_energy_with_calc(atoms, calc):
    try:
        atoms.calc = calc
        energy = float(atoms.get_potential_energy())
    except Exception as exc:
        raise CalculatorExecutionError(
            "Calculator failed while evaluating strain-scan potential energy: "
            f"{type(exc).__name__}: {exc}"
        ) from exc
    if not np.isfinite(energy):
        raise CalculatorExecutionError(
            "Calculator returned a non-finite strain-scan potential energy."
        )
    return energy
