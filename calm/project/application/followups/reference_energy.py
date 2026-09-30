"""Authoritative per-interface reference-energy calculations.

This module builds the strained-bulk or isolated-surface structures required by
CALM's explicit thermodynamic conventions, evaluates their raw total energies,
and persists one reference result per interface side.  Reference values remain
indexed by the authoritative source interface because different strain
partitions generally require different reference structures.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from math import gcd, isclose
from typing import Any, Mapping, Sequence

from calm.interface.energy.contract import (
    UnsupportedReferenceWorkflowError,
    _finite_float,
    _positive_integer,
    canonical_energy_formula,
    require_calculated_reference_support,
)
from calm.project.domain.contracts.energy_result import (
    ENERGY_RESULT_VERSION,
    REFERENCE_ENERGY_RESULT_SCHEMA,
)
from calm.project.domain.contracts.relaxed_reference import (
    RELAXED_SURFACE_PROTOCOL,
    canonical_surface_partition,
    canonical_surface_relaxation_settings,
    exact_nonnegative_integer,
    validate_relaxed_surface_summary,
)
from calm.serialization.regression import sha256_hex, deterministic_json
from ...domain.models import FollowupResult, Run
from ...ports.uow import UnitOfWork
from ..interface_prototype_payload import load_interface_prototype
from ..runs import RunsService
from .energy_backends import DeterministicEnergyBackend
from .common import persisted_followup_uid
from .orch_helpers import (
    finalize_run_state_and_refresh,
    persist_artifact_payloads,
    persist_followups_with_edges,
)


@dataclass
class ReferenceEnergyStageResult:
    source_interface_uid: str
    prototype_uid: str
    reference_kind: str
    side: str
    status: str
    run_uid: str | None = None
    followup_uid: str | None = None
    energy_eV: float | None = None
    energy_eV_per_formula_unit: float | None = None
    reason: Any = None


@dataclass
class _PreparedReferenceTarget:
    source_interface_uid_full: str
    prototype_uid_full: str
    reference_uid_full: str
    reference_kind: str
    side: str
    atoms: Any
    metadata: dict[str, Any]

    def identity_row(self) -> dict[str, Any]:
        row = {
            "source_interface_uid_full": self.source_interface_uid_full,
            "prototype_uid_full": self.prototype_uid_full,
            "reference_uid_full": self.reference_uid_full,
            "reference_kind": self.reference_kind,
            "side": self.side,
        }
        for key in (
            "source_bulk_uid_full",
            "source_slab_uid_full",
            "structure_fingerprint",
            "reference_formula_units",
            "interface_formula_units",
            "reference_protocol",
            "reference_area_A2",
            "source_interface_structure_fingerprint",
            "initial_surface_structure_fingerprint",
        ):
            if key in self.metadata:
                row[key] = self.metadata[key]
        return row


def _reference_step_count(value: object, *, relaxed_surface: bool) -> int:
    """Validate the backend step count for one reference calculation."""

    if relaxed_surface:
        return exact_nonnegative_integer(
            "Computed relaxed-reference step count",
            value,
        )
    return _positive_integer(
        value,
        name="Computed reference-energy step count",
    )


def _gauge_rotated_supercell_basis(atoms: Any, matrix: Any, rotation: Any):
    """Return the column-basis representation of ``R A N`` in the interface plane."""

    import numpy as np

    cell_columns = np.asarray(atoms.get_cell(), dtype=float).T
    supercell = np.eye(3, dtype=int)
    supercell[:2, :2] = np.asarray(matrix, dtype=int)
    gauge = np.eye(3, dtype=float)
    gauge[:2, :2] = np.asarray(rotation, dtype=float)
    basis = (gauge @ cell_columns @ supercell)[:2, :2]
    if not np.all(np.isfinite(basis)) or abs(float(np.linalg.det(basis))) <= 1e-14:
        raise ValueError("The gauge-rotated in-plane supercell basis is singular.")
    return basis


def _make_inplane_supercell(atoms: Any, matrix: Any):
    import numpy as np

    from calm.structure.ase_adapter import make_supercell_col

    m = np.asarray(matrix, dtype=int)
    if m.shape != (2, 2):
        raise ValueError(
            f"In-plane supercell matrix must have shape (2, 2); got {m.shape}."
        )
    p = np.array(
        [[m[0, 0], m[0, 1], 0], [m[1, 0], m[1, 1], 0], [0, 0, 1]],
        dtype=int,
    )
    return make_supercell_col(atoms, p)


def _set_common_inplane_cell(atoms: Any, target_basis: Any):
    out = atoms.copy()
    fractional = out.get_scaled_positions()
    cell = out.get_cell().copy()
    cell[:2, :2] = target_basis.T
    out.set_cell(cell, scale_atoms=False)
    out.set_scaled_positions(fractional)
    return out


def _reduced_formula_counts(atoms: Any) -> dict[str, int]:
    counts = Counter(str(symbol) for symbol in atoms.get_chemical_symbols())
    if not counts:
        raise ValueError("Cannot derive a formula unit from an empty structure.")
    divisor = 0
    for value in counts.values():
        divisor = gcd(divisor, int(value))
    if divisor < 1:
        raise ValueError("Cannot derive a reduced formula unit.")
    return {symbol: int(value) // divisor for symbol, value in sorted(counts.items())}


def _count_formula_units(
    atoms: Any,
    formula_counts: Mapping[str, int],
    *,
    label: str,
) -> int:
    counts = Counter(str(symbol) for symbol in atoms.get_chemical_symbols())
    if set(counts) != set(formula_counts):
        raise UnsupportedReferenceWorkflowError(
            f"{label} composition {dict(sorted(counts.items()))} is not an integer "
            f"multiple of bulk formula {dict(formula_counts)}. The current strained-bulk "
            "reference contract does not support non-stoichiometric reservoir terms."
        )
    ratios: set[int] = set()
    for symbol, coefficient in formula_counts.items():
        value = int(counts[symbol])
        if coefficient < 1 or value % int(coefficient) != 0:
            raise UnsupportedReferenceWorkflowError(
                f"{label} composition is not an integer multiple of the bulk formula. "
                "The current strained-bulk reference contract does not support "
                "non-stoichiometric reservoir terms."
            )
        ratios.add(value // int(coefficient))
    if len(ratios) != 1:
        raise UnsupportedReferenceWorkflowError(
            f"{label} composition is not an integer multiple of the bulk formula. "
            "The current strained-bulk reference contract does not support "
            "non-stoichiometric reservoir terms."
        )
    count = next(iter(ratios))
    if count < 1:
        raise ValueError(f"{label} must contain at least one formula unit.")
    return count


def _structure_fingerprint(atoms: Any) -> str:
    from calm.structure.payloads import atoms_to_dict

    payload = atoms_to_dict(atoms)
    return sha256_hex(deterministic_json(payload, float_ndigits=12))


def _interface_params(interface: Any) -> dict[str, Any]:
    value = getattr(interface, "params", None)
    if not isinstance(value, Mapping):
        raise TypeError("The source interface must expose exact current params.")
    return dict(value)


def _interface_alpha(interface: Any) -> float:
    _interface_params(interface)
    value = getattr(interface, "strain_alpha", None)
    if value is None:
        raise ValueError(
            "The source interface is missing an explicit strain_alpha. "
            "CALM will not guess "
            "the strain partition used for authoritative reference structures."
        )
    alpha = _finite_float(value, name="strain_alpha")
    if not 0.0 <= alpha <= 1.0:
        raise ValueError(f"strain_alpha must lie in [0, 1]; got {alpha!r}.")
    return alpha


def _require_supported_reference_cell_mode(
    interface: Any,
    *,
    formula: str,
) -> None:
    """Reject variable-cell interface states only for surface references."""

    relaxation_settings = dict(
        _interface_params(interface).get("relaxation_settings") or {}
    )
    if (
        formula != "interface_excess_strained_bulk"
        and bool(relaxation_settings.get("relax_cell"))
    ):
        raise UnsupportedReferenceWorkflowError(
            "Calculated isolated-surface references require fixed-cell interface "
            "relaxation. Variable-cell surface-reference protocols are unsupported."
        )


def _fixed_cell_relaxed_interface_context(interface: Any) -> dict[str, Any]:
    """Return verified provenance for one calculator-relaxed fixed-cell interface."""

    from calm.project.domain.contracts.relaxation import (
        canonical_relaxation_controls,
        validate_relaxation_result,
    )

    params = _interface_params(interface)
    if getattr(interface, "stage", None) != "relaxed":
        raise UnsupportedReferenceWorkflowError(
            "Relaxed isolated-surface references require an authoritative relaxed "
            "interface target."
        )
    if str(params.get("scientific_authority") or "") != "calculator_backed":
        raise UnsupportedReferenceWorkflowError(
            "Relaxed isolated-surface references require a calculator-backed "
            "interface relaxation."
        )
    settings = dict(params.get("relaxation_settings") or {})
    controls = canonical_relaxation_controls(
        protocol=params.get("protocol"),
        convergence={"force_tol": settings.get("fmax")},
        max_steps=settings.get("steps"),
        relax_cell=settings.get("relax_cell"),
    )
    if controls.relax_cell:
        raise UnsupportedReferenceWorkflowError(
            "Relaxed isolated-surface references require a fixed-cell interface "
            "relaxation so the interface and reference areas remain identical."
        )
    source_run_uid = params.get("source_run_uid")
    source_followup_uid = params.get("source_followup_uid")
    if not source_run_uid or not source_followup_uid:
        raise UnsupportedReferenceWorkflowError(
            "Relaxed isolated-surface references require persistent M12 run and "
            "follow-up lineage."
        )
    certificate = validate_relaxation_result(
        final_energy_eV=params.get("final_energy_eV"),
        n_steps=params.get("n_steps"),
        max_steps=params.get("max_steps"),
        converged=params.get("optimizer_reported_converged"),
        max_atomic_force_eV_per_A=params.get("max_force_eV_per_A"),
        max_optimizer_residual=params.get("max_optimizer_residual"),
        force_tolerance_eV_per_A=params.get("fmax_eV_per_A"),
    )
    if (
        certificate["max_steps"] != controls.max_steps
        or certificate["force_tolerance_eV_per_A"] != controls.force_tolerance_eV_per_A
    ):
        raise UnsupportedReferenceWorkflowError(
            "The relaxed-interface convergence certificate does not match its "
            "persisted M12 controls."
        )
    if not certificate["converged"] or not bool(params.get("residual_satisfied")):
        raise UnsupportedReferenceWorkflowError(
            "Relaxed isolated-surface references require a successful M12 "
            "convergence certificate."
        )
    return {
        "source_relaxation_run_uid_full": source_run_uid,
        "source_relaxation_followup_uid_full": source_followup_uid,
        "source_relaxation_backend": params.get("relaxation_backend"),
        "source_relaxation_settings": settings,
        "source_relaxation_convergence_certificate": certificate,
    }


def _center_surface_in_fixed_cell(atoms: Any) -> Any:
    """Center one periodic slab along the third fractional coordinate."""

    import numpy as np

    out = atoms.copy()
    scaled = np.asarray(out.get_scaled_positions(wrap=False), dtype=float)
    if scaled.ndim != 2 or scaled.shape != (len(out), 3):
        raise ValueError(
            "Isolated-surface fractional coordinates must have shape (N, 3)."
        )
    if not np.isfinite(scaled).all() or len(out) < 1:
        raise ValueError("Isolated-surface coordinates must be finite and non-empty.")
    z = np.mod(scaled[:, 2], 1.0)
    z[np.isclose(z, 1.0, rtol=0.0, atol=1e-14)] = 0.0
    ordered = np.sort(z)
    gaps = np.diff(np.concatenate([ordered, ordered[:1] + 1.0]))
    start = ordered[(int(np.argmax(gaps)) + 1) % len(ordered)]
    unwrapped = np.mod(z - start, 1.0)
    midpoint = 0.5 * (float(np.min(unwrapped)) + float(np.max(unwrapped)))
    scaled[:, 2] = np.mod(unwrapped + 0.5 - midpoint, 1.0)
    scaled[np.isclose(scaled, 1.0, rtol=0.0, atol=1e-14)] = 0.0
    out.set_scaled_positions(scaled)
    return out


def _authoritative_interface_area(atoms: Any) -> float:
    """Return the positive area of the evaluated interface in-plane cell."""

    import numpy as np

    cell = np.asarray(atoms.get_cell(), dtype=float)
    if cell.shape != (3, 3) or not np.isfinite(cell).all():
        raise ValueError("The relaxed interface cell must be a finite 3x3 matrix.")
    area = _finite_float(
        float(np.linalg.norm(np.cross(cell[0], cell[1]))),
        name="The relaxed-interface in-plane area",
    )
    if area <= 0.0:
        raise ValueError("The relaxed-interface in-plane area must be positive.")
    return area


def _load_interface_deformation_context(
    *,
    interface_uid_full: str,
    interface_atoms_loader: Any | None,
) -> tuple[Any, dict[str, Any]]:
    """Load authoritative interface atoms and exact deformation accounting."""

    if not callable(interface_atoms_loader):
        raise UnsupportedReferenceWorkflowError(
            "Calculated strained-bulk references require a loader for the "
            "authoritative interface atoms."
        )
    atoms = interface_atoms_loader(interface_uid_full)
    if atoms is None:
        raise ValueError("The source interface is missing its atomistic structure.")
    try:
        atoms = atoms.copy()
    except AttributeError as exc:
        raise TypeError(
            "The source interface atom payload must provide copy()."
        ) from exc

    from calm.slab.oriented.cell_contract import (
        validate_interface_deformation_provenance,
    )

    accounting = validate_interface_deformation_provenance(
        atoms,
        require_source=True,
    )
    return atoms, accounting


def _reference_deformation_state(
    accounting: Mapping[str, Any],
    *,
    side: str,
) -> tuple[Any, dict[str, Any]]:
    """Return the total slab-frame deformation for one reference side."""

    import numpy as np

    from calm.slab.oriented.cell_contract import (
        INTERFACE_DEFORMATION_ACCOUNTING_INFO_KEY,
        INTERFACE_RELAXATION_DEFORMATION_INFO_KEY,
    )

    side_name = {"a": "lower", "b": "upper"}.get(str(side).lower())
    if side_name is None:
        raise ValueError("Reference side must be 'a' or 'b'.")
    source = dict(accounting[INTERFACE_DEFORMATION_ACCOUNTING_INFO_KEY])
    source_side = dict(source[side_name])
    total = np.asarray(source_side["F_total_slab"], dtype=float)
    provenance: dict[str, Any] = {
        "policy": source["policy"],
        "version": source["version"],
        "state": "pre_relaxation",
        "F_construction_slab": source_side["F_construction_slab"],
        "F_interface_slab": source_side["F_interface_slab"],
        "F_total_pre_relaxation_slab": source_side["F_total_slab"],
    }

    relaxation = accounting.get(INTERFACE_RELAXATION_DEFORMATION_INFO_KEY)
    if relaxation is not None:
        relaxation = dict(relaxation)
        relaxed_side = dict(relaxation[side_name])
        total = np.asarray(
            relaxed_side["F_total_post_relaxation_slab"],
            dtype=float,
        )
        provenance.update(
            {
                "state": "post_relaxation",
                "relaxation_policy": relaxation["policy"],
                "relaxation_version": relaxation["version"],
                "relaxation_cell_mode": relaxation["cell_mode"],
                "relaxation_composition_count": relaxation[
                    "composition_count"
                ],
                "F_relaxation_interface": relaxation[
                    "F_relaxation_interface"
                ],
                "F_total_post_relaxation_slab": relaxed_side[
                    "F_total_post_relaxation_slab"
                ],
            }
        )
    if total.shape != (3, 3) or not np.isfinite(total).all():
        raise ValueError("Reference total deformation must be a finite 3x3 matrix.")
    determinant = float(np.linalg.det(total))
    if not np.isfinite(determinant) or determinant <= 0.0:
        raise ValueError("Reference total deformation must have positive determinant.")
    provenance["F_total_reference_slab"] = total.tolist()
    return total, provenance


def _map_reference_deformation_to_conventional(
    *,
    slab_atoms: Any,
    rotation_2d: Any,
    F_total_slab: Any,
    side: str,
) -> Any:
    """Map one authoritative total deformation into the bulk frame."""

    import numpy as np

    from calm.slab.oriented.cell_contract import slab_to_conventional_map

    rotation = np.asarray(rotation_2d, dtype=float)
    if (
        rotation.shape != (2, 2)
        or not np.isfinite(rotation).all()
        or not np.allclose(
            rotation.T @ rotation,
            np.eye(2),
            atol=1e-10,
            rtol=1e-10,
        )
    ):
        raise ValueError(
            f"Reference side {side.upper()} gauge must be a finite "
            "orthogonal 2x2 matrix."
        )
    determinant = float(np.linalg.det(rotation))
    if not np.isclose(abs(determinant), 1.0, atol=1e-10, rtol=1e-10):
        raise ValueError(
            f"Reference side {side.upper()} gauge must have determinant +1 or -1."
        )
    gauge = np.eye(3, dtype=float)
    gauge[:2, :2] = rotation
    slab_to_conv = slab_to_conventional_map(
        slab_atoms,
        gauge_rotation=gauge,
        name=f"Reference side {side.upper()} source slab",
    )
    if slab_to_conv is None:
        raise UnsupportedReferenceWorkflowError(
            "Calculated strained-bulk references require exact current "
            "slab-to-conventional transform provenance."
        )
    total = np.asarray(F_total_slab, dtype=float)
    mapped = slab_to_conv @ total @ slab_to_conv.T
    determinant = float(np.linalg.det(mapped))
    if (
        mapped.shape != (3, 3)
        or not np.isfinite(mapped).all()
        or not np.isfinite(determinant)
        or determinant <= 0.0
    ):
        raise ValueError(
            "Mapped strained-bulk reference deformation must be finite and "
            "orientation-preserving."
        )
    return mapped


def _apply_bulk_deformation(atoms: Any, deformation: Any) -> Any:
    """Apply one homogeneous Cartesian deformation to a pristine bulk cell."""

    import numpy as np

    out = atoms.copy()
    cell_columns = np.asarray(out.get_cell(), dtype=float).T
    F = np.asarray(deformation, dtype=float)
    out.set_cell((F @ cell_columns).T, scale_atoms=True)
    return out


def _validate_reference_target_basis(
    *,
    slab_atoms: Any,
    matrix: Any,
    rotation: Any,
    F_total_slab: Any,
    target_basis: Any,
    side: str,
) -> None:
    """Require authoritative deformation to reproduce the interface basis."""

    import numpy as np

    source = _gauge_rotated_supercell_basis(slab_atoms, matrix, rotation)
    deformation = np.asarray(F_total_slab, dtype=float)
    expected = deformation[:2, :2] @ source
    target = np.asarray(target_basis, dtype=float)
    scale = max(
        1.0,
        float(np.linalg.norm(expected, ord=np.inf)),
        float(np.linalg.norm(target, ord=np.inf)),
    )
    if not np.allclose(expected, target, atol=1e-10 * scale, rtol=0.0):
        raise ValueError(
            f"Reference side {side.upper()} deformation accounting does not "
            "reproduce the authoritative interface in-plane basis."
        )


def _prepare_relaxed_surface_targets(
    *,
    interface: Any,
    prototype_uid_full: str,
    interface_uid_full: str,
    interface_atoms_loader: Any,
    expected_surface_a: Any,
    expected_surface_b: Any,
    reconstructed_area_A2: float,
    shared: Mapping[str, Any],
) -> list[_PreparedReferenceTarget]:
    """Cleave ordered slab blocks from the final relaxed interface."""

    import numpy as np

    context = _fixed_cell_relaxed_interface_context(interface)
    if not callable(interface_atoms_loader):
        raise UnsupportedReferenceWorkflowError(
            "Relaxed isolated-surface references require a loader for the persisted "
            "relaxed interface atoms."
        )
    atoms = interface_atoms_loader(interface_uid_full)
    if atoms is None:
        raise ValueError("The relaxed interface is missing its atomistic structure.")
    try:
        atoms = atoms.copy()
    except Exception as exc:
        raise TypeError("The relaxed interface atom payload is not copyable.") from exc

    n_a, n_b = canonical_surface_partition(
        n_total=len(atoms),
        n_side_a=len(expected_surface_a),
        n_side_b=len(expected_surface_b),
    )
    expected_numbers = np.concatenate(
        [
            np.asarray(expected_surface_a.get_atomic_numbers(), dtype=int),
            np.asarray(expected_surface_b.get_atomic_numbers(), dtype=int),
        ]
    )
    actual_numbers = np.asarray(atoms.get_atomic_numbers(), dtype=int)
    if not np.array_equal(actual_numbers, expected_numbers):
        raise ValueError(
            "The relaxed interface atom ordering or species no longer matches the "
            "authoritative lower/upper slab partition."
        )
    area = _authoritative_interface_area(atoms)
    if not np.isclose(area, reconstructed_area_A2, rtol=1e-10, atol=1e-10):
        raise UnsupportedReferenceWorkflowError(
            "The final relaxed interface area differs from the fixed-cell reference "
            "construction. Variable-cell post-relaxation references are unsupported."
        )

    source_fingerprint = _structure_fingerprint(atoms)
    surfaces = (
        ("a", _center_surface_in_fixed_cell(atoms[:n_a])),
        ("b", _center_surface_in_fixed_cell(atoms[n_a : n_a + n_b])),
    )
    targets: list[_PreparedReferenceTarget] = []
    for side, surface in surfaces:
        kind = f"relaxed_surface_{side}"
        initial_fingerprint = _structure_fingerprint(surface)
        metadata = {
            **dict(shared),
            **context,
            "reference_protocol": RELAXED_SURFACE_PROTOCOL,
            "reference_area_A2": area,
            "source_interface_structure_fingerprint": source_fingerprint,
            "initial_surface_structure_fingerprint": initial_fingerprint,
            "surface_atom_count": len(surface),
        }
        ref_uid = "reference:" + sha256_hex(
            deterministic_json(
                {
                    "source_interface_uid_full": interface_uid_full,
                    "reference_kind": kind,
                    "reference_protocol": RELAXED_SURFACE_PROTOCOL,
                    "initial_surface_structure_fingerprint": initial_fingerprint,
                },
                float_ndigits=12,
            )
        )
        targets.append(
            _PreparedReferenceTarget(
                source_interface_uid_full=interface_uid_full,
                prototype_uid_full=prototype_uid_full,
                reference_uid_full=ref_uid,
                reference_kind=kind,
                side=side,
                atoms=surface,
                metadata=metadata,
            )
        )
    return targets


def _prepare_interface_targets(  # noqa: C901
    uow: Any,
    *,
    interface_uid_full: str,
    formula: str,
    interface_atoms_loader: Any | None = None,
) -> list[_PreparedReferenceTarget]:
    import numpy as np

    from calm.interface.refinement.partition import strain_partition_inplane

    interface = uow.derived_interfaces.get_by_uid_full(interface_uid_full)
    if interface is None:
        raise KeyError(f"Derived interface not found: {interface_uid_full}")
    prototype_uid_full = interface.prototype_uid_full
    prototype = load_interface_prototype(uow, prototype_uid_full)
    matrix_a = prototype.supercell_a.N_tot
    matrix_b = prototype.supercell_b.N_tot
    rotation_a = prototype.supercell_a.R_sup
    rotation_b = prototype.supercell_b.R_sup
    alpha = _interface_alpha(interface)
    _require_supported_reference_cell_mode(interface, formula=formula)

    slab_a = prototype.slab_a
    slab_b = prototype.slab_b
    if slab_a.atoms is None or slab_b.atoms is None:
        raise ValueError(
            "Prototype source slabs are missing authoritative atom payloads."
        )

    surface_a = _make_inplane_supercell(slab_a.atoms, matrix_a)
    surface_b = _make_inplane_supercell(slab_b.atoms, matrix_b)
    deformation_accounting: dict[str, Any] | None = None

    if formula == "interface_excess_strained_bulk":
        interface_atoms, deformation_accounting = (
            _load_interface_deformation_context(
                interface_uid_full=interface_uid_full,
                interface_atoms_loader=interface_atoms_loader,
            )
        )
        from calm.slab.oriented.cell_contract import (
            require_interface_ready_slab_cell,
        )

        cell = np.asarray(interface_atoms.get_cell(), dtype=float)
        require_interface_ready_slab_cell(
            cell,
            name="Calculated-reference source interface cell",
        )
        target_basis = cell[:2, :2].T
        target_area_A2 = _authoritative_interface_area(interface_atoms)
        source_interface_fingerprint = _structure_fingerprint(interface_atoms)
    else:
        basis_a = _gauge_rotated_supercell_basis(
            slab_a.atoms, matrix_a, rotation_a
        )
        basis_b = _gauge_rotated_supercell_basis(
            slab_b.atoms, matrix_b, rotation_b
        )
        partition = strain_partition_inplane(basis_a, basis_b, alpha=alpha)
        target_basis = partition.X
        target_area_A2 = _finite_float(
            abs(float(np.linalg.det(np.asarray(target_basis, dtype=float)))),
            name="The calculated-reference in-plane area",
        )
        if target_area_A2 <= 0.0:
            raise ValueError(
                "The calculated-reference in-plane area must be positive."
            )
        surface_a = _set_common_inplane_cell(surface_a, target_basis)
        surface_b = _set_common_inplane_cell(surface_b, target_basis)
        source_interface_fingerprint = None

    shared = {
        "formula_id": formula,
        "strain_alpha": alpha,
        "target_inplane_basis_A": np.asarray(
            target_basis, dtype=float
        ).tolist(),
        "reference_area_A2": target_area_A2,
        "supercell_matrix_a": matrix_a.tolist(),
        "supercell_matrix_b": matrix_b.tolist(),
        "orthogonal_gauge_a": rotation_a.tolist(),
        "orthogonal_gauge_b": rotation_b.tolist(),
    }
    if source_interface_fingerprint is not None:
        shared["source_interface_structure_fingerprint"] = (
            source_interface_fingerprint
        )

    targets: list[_PreparedReferenceTarget] = []
    if formula == "work_of_adhesion_relaxed_surfaces":
        return _prepare_relaxed_surface_targets(
            interface=interface,
            prototype_uid_full=prototype_uid_full,
            interface_uid_full=interface_uid_full,
            interface_atoms_loader=interface_atoms_loader,
            expected_surface_a=surface_a,
            expected_surface_b=surface_b,
            reconstructed_area_A2=target_area_A2,
            shared=shared,
        )

    if formula == "work_of_separation_unrelaxed_surfaces":
        for side, slab, atoms in (
            ("a", slab_a, surface_a),
            ("b", slab_b, surface_b),
        ):
            metadata = {
                **shared,
                "source_slab_uid_full": slab.uid_full,
                "source_bulk_uid_full": slab.bulk_uid_full,
                "structure_fingerprint": _structure_fingerprint(atoms),
            }
            kind = f"isolated_surface_{side}"
            ref_uid = "reference:" + sha256_hex(
                deterministic_json(
                    {
                        "source_interface_uid_full": interface_uid_full,
                        "reference_kind": kind,
                        "structure_fingerprint": metadata[
                            "structure_fingerprint"
                        ],
                    },
                    float_ndigits=12,
                )
            )
            targets.append(
                _PreparedReferenceTarget(
                    source_interface_uid_full=interface_uid_full,
                    prototype_uid_full=prototype_uid_full,
                    reference_uid_full=ref_uid,
                    reference_kind=kind,
                    side=side,
                    atoms=atoms,
                    metadata=metadata,
                )
            )
        return targets

    if formula != "interface_excess_strained_bulk":
        raise ValueError(f"Unsupported first-class reference formula: {formula!r}")
    assert deformation_accounting is not None

    for side, slab, surface_atoms, rotation in (
        ("a", slab_a, surface_a, rotation_a),
        ("b", slab_b, surface_b, rotation_b),
    ):
        bulk = uow.bulks.get_by_uid_full(slab.bulk_uid_full)
        if bulk is None or bulk.atoms_conventional is None:
            raise ValueError(
                f"Source bulk {slab.bulk_uid_full!r} is missing an authoritative "
                "conventional-cell structure."
            )
        F_total_slab, deformation_provenance = _reference_deformation_state(
            deformation_accounting,
            side=side,
        )
        _validate_reference_target_basis(
            slab_atoms=slab.atoms,
            matrix=matrix_a if side == "a" else matrix_b,
            rotation=rotation,
            F_total_slab=F_total_slab,
            target_basis=target_basis,
            side=side,
        )
        F_total_conv = _map_reference_deformation_to_conventional(
            slab_atoms=slab.atoms,
            rotation_2d=rotation,
            F_total_slab=F_total_slab,
            side=side,
        )
        bulk_reference = _apply_bulk_deformation(
            bulk.atoms_conventional,
            F_total_conv,
        )
        deformation_provenance["F_total_reference_conventional"] = (
            np.asarray(F_total_conv, dtype=float).tolist()
        )

        formula_counts = _reduced_formula_counts(bulk.atoms_conventional)
        reference_formula_units = _count_formula_units(
            bulk_reference,
            formula_counts,
            label=f"strained bulk {side.upper()} reference cell",
        )
        interface_formula_units = _count_formula_units(
            surface_atoms,
            formula_counts,
            label=f"interface side {side.upper()}",
        )
        metadata = {
            **shared,
            "source_slab_uid_full": slab.uid_full,
            "source_bulk_uid_full": bulk.uid_full,
            "bulk_formula_counts": dict(formula_counts),
            "reference_formula_units": reference_formula_units,
            "interface_formula_units": interface_formula_units,
            "deformation_accounting": deformation_provenance,
            "structure_fingerprint": _structure_fingerprint(bulk_reference),
        }
        kind = f"strained_bulk_{side}"
        ref_uid = "reference:" + sha256_hex(
            deterministic_json(
                {
                    "source_interface_uid_full": interface_uid_full,
                    "reference_kind": kind,
                    "structure_fingerprint": metadata[
                        "structure_fingerprint"
                    ],
                },
                float_ndigits=12,
            )
        )
        targets.append(
            _PreparedReferenceTarget(
                source_interface_uid_full=interface_uid_full,
                prototype_uid_full=prototype_uid_full,
                reference_uid_full=ref_uid,
                reference_kind=kind,
                side=side,
                atoms=bulk_reference,
                metadata=metadata,
            )
        )
    return targets


class ReferenceEnergyOrchestrator:
    """Run synchronous, persistent reference-energy calculations."""

    def __init__(
        self,
        uow: UnitOfWork,
        *,
        interface_atoms_loader: Any | None = None,
        artifacts: Any | None = None,
    ) -> None:
        if hasattr(uow, "_depth") and getattr(uow, "_depth", 0) > 0:
            raise ValueError(
                "Do not construct ReferenceEnergyOrchestrator with an entered "
                "UnitOfWork."
            )
        self._uow = uow
        self._runs = RunsService(uow=uow)
        self._backend = DeterministicEnergyBackend()
        self._backend_name = "deterministic"
        self._interface_atoms_loader = interface_atoms_loader
        self._artifacts = artifacts

    def with_backend(self, backend: Any) -> "ReferenceEnergyOrchestrator":
        self._backend = backend
        name = (
            getattr(backend, "name", None)
            or getattr(backend, "__name__", None)
            or type(backend).__name__
        )
        self._backend_name = str(name).strip().lower()
        return self

    def _backend_identity(
        self,
        targets: Sequence[_PreparedReferenceTarget],
    ) -> dict[str, Any]:
        rows = [target.identity_row() for target in targets]
        identity = getattr(self._backend, "identity", None)
        if callable(identity):
            value = identity(targets=rows, uow=self._uow)
            if not isinstance(value, Mapping):
                raise TypeError("Energy backend identity() must return a mapping.")
            return dict(value)
        return {
            "name": self._backend_name,
            "class": (
                f"{type(self._backend).__module__}.{type(self._backend).__qualname__}"
            ),
        }

    def _existing(self, run_uid_full: str) -> dict[tuple[str, str], FollowupResult]:
        out: dict[tuple[str, str], FollowupResult] = {}
        with self._uow as uow:
            for row in uow.followups.list(
                run_uid_full=run_uid_full,
                kind="reference_energy",
                limit=100000,
            ):
                if str(row.status) not in {"done", "completed"}:
                    continue
                payload = dict(row.payload or {})
                reference = payload.get("reference")
                if not isinstance(reference, Mapping):
                    raise ValueError(
                        f"Persisted reference-energy follow-up {row.uid_full!r} "
                        "is missing exact reference identity."
                    )
                interface_uid = row.target_uid_full
                reference_kind = reference.get("kind")
                if not interface_uid or not reference_kind:
                    raise ValueError(
                        f"Persisted reference-energy follow-up {row.uid_full!r} "
                        "is missing source-interface or reference-kind identity."
                    )
                out[(str(interface_uid), str(reference_kind))] = row
        return out

    def run_stage(  # noqa: C901
        self,
        *,
        interfaces: Sequence[str],
        formula: str,
        calculation: Mapping[str, Any] | None = None,
        payload: Mapping[str, Any] | None = None,
        resume: bool = True,
        partial_resume: bool = True,
    ) -> tuple[Run, list[ReferenceEnergyStageResult]]:
        formula, _quantity = canonical_energy_formula(formula)
        require_calculated_reference_support(formula)

        calculation_dict = dict(calculation or {"mode": "single_point"})
        calculation_dict.setdefault("mode", "single_point")
        relaxation_settings = None
        if formula == "work_of_adhesion_relaxed_surfaces":
            relaxation_settings = canonical_surface_relaxation_settings(
                calculation_dict.get("reference_relaxation")
            )
            calculation_dict["reference_relaxation"] = dict(relaxation_settings)
        elif calculation_dict.get("reference_relaxation") is not None:
            raise ValueError(
                "reference_relaxation settings are used only by "
                "work_of_adhesion_relaxed_surfaces."
            )
        user_payload = dict(payload or {})

        prepared: list[_PreparedReferenceTarget] = []
        with self._uow as uow:
            for identifier in interfaces:
                uid = uow.ids.resolve(str(identifier), expected_tag="i")
                prepared.extend(
                    _prepare_interface_targets(
                        uow,
                        interface_uid_full=uid,
                        formula=formula,
                        interface_atoms_loader=self._interface_atoms_loader,
                    )
                )

        backend_identity = self._backend_identity(prepared)
        spec = {
            "kind": "reference_energy",
            "formula_id": formula,
            "targets": sorted(
                (target.identity_row() for target in prepared),
                key=lambda row: (
                    str(row["source_interface_uid_full"]),
                    str(row["reference_kind"]),
                ),
            ),
            "backend": dict(backend_identity),
            "calculation": dict(calculation_dict),
            "impl": "typed_persistent_v3",
        }
        run = self._runs.create(run_type="reference_energy", spec=spec)

        if resume and run.status == "done":
            return run, [
                ReferenceEnergyStageResult(
                    source_interface_uid=target.source_interface_uid_full,
                    prototype_uid=target.prototype_uid_full,
                    reference_kind=target.reference_kind,
                    side=target.side,
                    status="skipped",
                    run_uid=run.uid_full,
                    reason="run_already_done",
                )
                for target in prepared
            ]

        self._runs.mark_running(
            run.uid_full,
            progress={"stage": "reference_energy", "n_requested": len(prepared)},
        )
        existing = self._existing(run.uid_full) if partial_resume else {}
        stage_results: list[ReferenceEnergyStageResult] = []
        completed: list[FollowupResult] = []

        with self._uow as uow:
            for target in prepared:
                key = (target.source_interface_uid_full, target.reference_kind)
                if key in existing:
                    row = existing[key]
                    row_payload = dict(row.payload or {})
                    stage_results.append(
                        ReferenceEnergyStageResult(
                            source_interface_uid=target.source_interface_uid_full,
                            prototype_uid=target.prototype_uid_full,
                            reference_kind=target.reference_kind,
                            side=target.side,
                            status="skipped",
                            run_uid=run.uid_full,
                            followup_uid=row.uid_full,
                            energy_eV=row_payload["energy"]["total_eV"],
                            energy_eV_per_formula_unit=row_payload["energy"][
                                "per_formula_unit_eV"
                            ],
                            reason="existing_followup",
                        )
                    )
                    continue

                followup_uid = persisted_followup_uid(
                    run_uid_full=run.uid_full,
                    prototype_uid_full=target.prototype_uid_full,
                    target_uid_full=target.source_interface_uid_full,
                    target_kind="interface",
                    kind="reference_energy",
                    qualifiers={"reference_kind": target.reference_kind},
                )
                followup_id = uow.ids.ensure_short_id(uid_full=followup_uid, tag="f")
                config = dict(calculation_dict)
                config["target_atoms"] = target.atoms
                try:
                    computed = self._backend.compute(
                        run_uid=run.uid_full,
                        prototype_uid=target.prototype_uid_full,
                        target_uid=target.reference_uid_full,
                        config=config,
                        uow=uow,
                    )
                    energy = _finite_float(
                        computed.energy,
                        name="Computed reference total energy",
                    )
                    if formula == "work_of_adhesion_relaxed_surfaces":
                        n_steps = _reference_step_count(
                            computed.n_steps,
                            relaxed_surface=True,
                        )
                        relaxation_summary = validate_relaxed_surface_summary(
                            getattr(computed, "relaxation_summary", None),
                            settings=relaxation_settings or {},
                        )
                        relaxed_atoms = getattr(computed, "relaxed_atoms", None)
                        if relaxed_atoms is None:
                            raise ValueError(
                                "Relaxed surface computation did not return the "
                                "final atomistic structure."
                            )
                        from calm.project.domain.contracts.relaxation import (
                            validate_relaxed_structure_transition,
                        )

                        verified_transition = validate_relaxed_structure_transition(
                            initial_positions=target.atoms.get_positions(),
                            final_positions=relaxed_atoms.get_positions(),
                            initial_cell=target.atoms.get_cell(),
                            final_cell=relaxed_atoms.get_cell(),
                            initial_numbers=(target.atoms.get_atomic_numbers()),
                            final_numbers=(relaxed_atoms.get_atomic_numbers()),
                            initial_pbc=target.atoms.get_pbc(),
                            final_pbc=relaxed_atoms.get_pbc(),
                            cell_mode="fixed",
                        )
                        relaxation_summary.update(verified_transition)
                        final_structure_fingerprint = _structure_fingerprint(
                            relaxed_atoms
                        )
                        final_area = _authoritative_interface_area(relaxed_atoms)
                        if not isclose(
                            final_area,
                            float(target.metadata["reference_area_A2"]),
                            rel_tol=1e-10,
                            abs_tol=1e-10,
                        ):
                            raise ValueError(
                                "Relaxed surface cell area changed during the "
                                "fixed-cell "
                                "reference protocol."
                            )
                    else:
                        n_steps = _reference_step_count(
                            computed.n_steps,
                            relaxed_surface=False,
                        )
                        relaxation_summary = None
                        final_structure_fingerprint = None
                except Exception as exc:
                    failure = {
                        "message": str(exc),
                        "exception_type": type(exc).__name__,
                        "module": type(exc).__module__,
                    }
                    reference_metadata = {
                        key: value
                        for key, value in target.metadata.items()
                        if key != "formula_id"
                    }
                    failed_payload = {
                        "schema": REFERENCE_ENERGY_RESULT_SCHEMA,
                        "version": ENERGY_RESULT_VERSION,
                        "result_stage": "reference_failed",
                        "reference": {
                            "uid_full": target.reference_uid_full,
                            "kind": target.reference_kind,
                            "side": target.side,
                            "formula_id": formula,
                            "metadata": reference_metadata,
                        },
                        "backend": {
                            "name": self._backend_name,
                            "identity": dict(backend_identity),
                            "settings": {
                                key: value
                                for key, value in calculation_dict.items()
                                if key != "reference_relaxation"
                            },
                        },
                        "relaxation": (
                            {
                                "settings": dict(relaxation_settings or {}),
                                "summary": {},
                                "final_structure_fingerprint": None,
                            }
                            if formula == "work_of_adhesion_relaxed_surfaces"
                            else None
                        ),
                        "workflow_metadata": dict(user_payload),
                        "failure": failure,
                    }
                    failed = FollowupResult(
                        uid_full=followup_uid,
                        id_short=followup_id,
                        run_uid_full=run.uid_full,
                        run_id_short=run.id_short,
                        prototype_uid_full=target.prototype_uid_full,
                        prototype_id_short=uow.ids.ensure_prototype_id(
                            target.prototype_uid_full
                        ),
                        target_uid_full=target.source_interface_uid_full,
                        target_kind="interface",
                        kind="reference_energy",
                        status="failed",
                        best_energy=None,
                        param1=None,
                        param2=None,
                        n_points=None,
                        payload=failed_payload,
                    )
                    persist_followups_with_edges(uow=uow, followups=[failed])
                    stage_results.append(
                        ReferenceEnergyStageResult(
                            source_interface_uid=target.source_interface_uid_full,
                            prototype_uid=target.prototype_uid_full,
                            reference_kind=target.reference_kind,
                            side=target.side,
                            status="failed",
                            run_uid=run.uid_full,
                            followup_uid=followup_uid,
                            reason=str(exc),
                        )
                    )
                    continue

                energy_per_fu = None
                reference_formula_units = target.metadata.get("reference_formula_units")
                if reference_formula_units is not None:
                    reference_formula_units = _positive_integer(
                        reference_formula_units,
                        name="Reference formula-unit count",
                    )
                    energy_per_fu = energy / reference_formula_units
                artifact_refs = persist_artifact_payloads(
                    uow=uow,
                    run_uid=run.uid_full,
                    proto_uid=target.prototype_uid_full,
                    target_uid=target.reference_uid_full,
                    artifact_payloads=computed.artifact_payloads,
                    artifacts=self._artifacts,
                )
                reference_metadata = {
                    key: value
                    for key, value in target.metadata.items()
                    if key != "formula_id"
                }
                row_payload = {
                    "schema": REFERENCE_ENERGY_RESULT_SCHEMA,
                    "version": ENERGY_RESULT_VERSION,
                    "result_stage": "reference_evaluated",
                    "reference": {
                        "uid_full": target.reference_uid_full,
                        "kind": target.reference_kind,
                        "side": target.side,
                        "formula_id": formula,
                        "metadata": reference_metadata,
                    },
                    "energy": {
                        "total_eV": energy,
                        "per_formula_unit_eV": energy_per_fu,
                        "n_steps": n_steps,
                    },
                    "backend": {
                        "name": self._backend_name,
                        "identity": dict(backend_identity),
                        "settings": {
                            key: value
                            for key, value in calculation_dict.items()
                            if key != "reference_relaxation"
                        },
                    },
                    "relaxation": (
                        {
                            "settings": dict(relaxation_settings or {}),
                            "summary": dict(relaxation_summary or {}),
                            "final_structure_fingerprint": (
                                final_structure_fingerprint
                            ),
                        }
                        if formula == "work_of_adhesion_relaxed_surfaces"
                        else None
                    ),
                    "workflow_metadata": dict(user_payload),
                    "artifact_refs": artifact_refs,
                    "summary": dict(computed.summary or {}),
                }
                followup = FollowupResult(
                    uid_full=followup_uid,
                    id_short=followup_id,
                    run_uid_full=run.uid_full,
                    run_id_short=run.id_short,
                    prototype_uid_full=target.prototype_uid_full,
                    prototype_id_short=uow.ids.ensure_prototype_id(
                        target.prototype_uid_full
                    ),
                    target_uid_full=target.source_interface_uid_full,
                    target_kind="interface",
                    kind="reference_energy",
                    status="done",
                    best_energy=energy,
                    param1=energy_per_fu,
                    param2=(
                        float(target.metadata["interface_formula_units"])
                        if target.metadata.get("interface_formula_units") is not None
                        else None
                    ),
                    n_points=n_steps,
                    payload=row_payload,
                )
                completed.append(followup)
                stage_results.append(
                    ReferenceEnergyStageResult(
                        source_interface_uid=target.source_interface_uid_full,
                        prototype_uid=target.prototype_uid_full,
                        reference_kind=target.reference_kind,
                        side=target.side,
                        status="completed",
                        run_uid=run.uid_full,
                        followup_uid=followup_uid,
                        energy_eV=energy,
                        energy_eV_per_formula_unit=energy_per_fu,
                    )
                )

            if completed:
                persist_followups_with_edges(uow=uow, followups=completed)
                for row in completed:
                    payload_row = dict(row.payload or {})
                    reference = dict(payload_row["reference"])
                    reference_metadata = dict(reference["metadata"])
                    for source_key in ("source_bulk_uid_full", "source_slab_uid_full"):
                        source_uid = reference_metadata.get(source_key)
                        if not source_uid:
                            continue
                        uow.edges.add(
                            src_uid_full=str(source_uid),
                            dst_uid_full=row.uid_full,
                            kind="reference_source_to_followup",
                            payload={
                                "reference_kind": reference["kind"],
                                "source_role": source_key,
                            },
                        )

        run = finalize_run_state_and_refresh(
            self._runs,
            run,
            stage_results,
            n_requested=len(prepared),
        )
        return run, stage_results
