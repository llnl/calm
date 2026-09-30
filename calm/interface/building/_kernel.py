"""Internal interface-build kernel.

This module isolates deterministic *geometry assembly* for building an atomistic
interface from two slab geometries plus a strain state and build parameters.

Design goals
------------
- No persistence/workflow dependencies (pure geometry).
- Deterministic normalization for translation parameters.
- Unit-testable in isolation.

This module is intentionally internal (private) and not part of the public API.
"""

from __future__ import annotations

from collections.abc import MutableMapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from calm.interface.building import _geometry as _bg
from calm.keys.uid import wrap01
from calm.slab.oriented.cell_contract import (
    INTERFACE_DEFORMATION_ACCOUNTING_INFO_KEY,
    SLAB_DEFORMATION_ACCOUNTING_POLICY,
    SLAB_DEFORMATION_ACCOUNTING_VERSION,
    SlabDeformationComposition,
    canonical_interface_deformation_accounting,
    compose_slab_deformations,
    require_interface_ready_slab_cell,
    require_interface_stackable_slab,
)


@dataclass(frozen=True)
class InterfaceDeformationAccounting:
    """Composed deformation provenance for both source slabs."""

    lower: SlabDeformationComposition
    upper: SlabDeformationComposition
    policy: str = SLAB_DEFORMATION_ACCOUNTING_POLICY
    version: int = SLAB_DEFORMATION_ACCOUNTING_VERSION


@dataclass(frozen=True)
class PreparedInterfaceStructure:
    """Translation-independent state for repeated interface construction.

    The stored slab objects have already undergone supercell construction,
    Cartesian gauge rotation, strain partitioning, out-of-plane placement, and
    final-cell assignment.  They remain private templates: every translated
    interface is assembled from fresh copies so callers and calculator backends
    cannot mutate the prepared state.
    """

    template_atoms: Any
    lower_indices: np.ndarray
    upper_indices: np.ndarray
    c1: np.ndarray
    c2: np.ndarray
    Lz: float
    deformation_accounting: InterfaceDeformationAccounting | None = None


def _deformation_accounting_payload(
    accounting: InterfaceDeformationAccounting,
) -> dict[str, Any]:
    """Return one validated JSON-native accounting payload."""

    def side_payload(side: SlabDeformationComposition) -> dict[str, Any]:
        return {
            "F_construction_slab": side.F_construction.tolist(),
            "F_interface_slab": side.F_interface.tolist(),
            "F_total_slab": side.F_total.tolist(),
        }

    return canonical_interface_deformation_accounting(
        {
            "policy": accounting.policy,
            "version": int(accounting.version),
            "lower": side_payload(accounting.lower),
            "upper": side_payload(accounting.upper),
        }
    )


@dataclass(frozen=True)
class BuiltInterfaceStructure:
    """Private return type for :func:`build_interface_atoms`.

    Attributes
    ----------
    atoms
        Built interface structure as an ASE Atoms-like object.
    lower_indices
        Indices into ``atoms`` that correspond to the lower slab.
    upper_indices
        Indices into ``atoms`` that correspond to the upper slab.
    c1, c2
        The in-plane cell vectors (Cartesian) after supercell + rotation + strain.
    Lz
        The out-of-plane cell length.
    """

    atoms: Any
    lower_indices: np.ndarray
    upper_indices: np.ndarray
    c1: np.ndarray
    c2: np.ndarray
    Lz: float
    deformation_accounting: InterfaceDeformationAccounting | None = None


def _nonnegative_integer(name: str, value: Any) -> int:
    """Return an exact nonnegative integer without truncation."""

    if isinstance(value, bool):
        raise TypeError(f"{name} must be a nonnegative integer.")
    if isinstance(value, (int, np.integer)):
        result = int(value)
    else:
        try:
            numeric = float(value)
        except (TypeError, ValueError) as exc:
            raise TypeError(f"{name} must be a nonnegative integer.") from exc
        if not np.isfinite(numeric) or not numeric.is_integer():
            raise ValueError(f"{name} must be a finite nonnegative integer.")
        result = int(numeric)
    if result < 0:
        raise ValueError(f"{name} must be a nonnegative integer.")
    return result


def _finite_nonnegative_float(name: str, value: Any) -> float:
    """Return a finite nonnegative scalar."""

    result = float(value)
    if not np.isfinite(result) or result < 0.0:
        raise ValueError(f"{name} must be non-negative and finite.")
    return result


def _exact_integer_matrix(name: str, value: Any, shape: tuple[int, int]) -> np.ndarray:
    """Return an exact finite integer matrix without truncation."""

    array = np.asarray(value)
    if array.shape != shape:
        raise ValueError(f"{name} must have shape {shape}; got {array.shape}.")
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


def _finite_matrix(name: str, value: Any, shape: tuple[int, int]) -> np.ndarray:
    """Return a finite floating-point matrix of the required shape."""

    matrix = np.asarray(value, dtype=float)
    if matrix.shape != shape:
        raise ValueError(f"{name} must have shape {shape}; got {matrix.shape}.")
    if not np.all(np.isfinite(matrix)):
        raise ValueError(f"{name} must contain only finite values.")
    return matrix


def _validate_supercell_matrix(name: str, value: Any) -> np.ndarray:
    """Validate one in-plane 3D supercell embedding."""

    matrix = _exact_integer_matrix(name, value, (3, 3))
    if not np.array_equal(matrix[2], np.array([0, 0, 1])):
        raise ValueError(f"{name} must leave the third lattice direction unchanged.")
    if not np.array_equal(matrix[:2, 2], np.zeros(2, dtype=int)):
        raise ValueError(f"{name} must not mix the third lattice direction in-plane.")
    determinant = int(matrix[0, 0]) * int(matrix[1, 1]) - int(matrix[0, 1]) * int(
        matrix[1, 0]
    )
    if determinant == 0:
        raise ValueError(f"{name} must have a nonzero in-plane determinant.")
    return matrix


def _validate_inplane_orthogonal_gauge(name: str, value: Any) -> np.ndarray:
    """Validate one orthogonal Cartesian gauge that preserves the z axis.

    Matching canonicalization may return either determinant sign.  A reflected
    orthogonal gauge is valid when its sign is paired with the signed integer
    supercell map so the resulting physical in-plane basis is right-handed.
    """

    matrix = _finite_matrix(name, value, (3, 3))
    tolerance = 1.0e-10
    if not np.allclose(matrix.T @ matrix, np.eye(3), atol=tolerance, rtol=tolerance):
        raise ValueError(f"{name} must be orthogonal.")
    determinant = float(np.linalg.det(matrix))
    if not np.isclose(abs(determinant), 1.0, atol=tolerance, rtol=tolerance):
        raise ValueError(f"{name} must have determinant +1 or -1.")
    expected_z = np.array([0.0, 0.0, 1.0])
    if not np.allclose(matrix[:, 2], expected_z, atol=tolerance, rtol=0.0):
        raise ValueError(f"{name} must preserve the global Cartesian z axis.")
    if not np.allclose(matrix[2, :], expected_z, atol=tolerance, rtol=0.0):
        raise ValueError(f"{name} must preserve the global Cartesian z axis.")
    return matrix


def _validate_inplane_deformation(name: str, value: Any) -> np.ndarray:
    """Validate one orientation-preserving in-plane Cartesian deformation."""

    matrix = _finite_matrix(name, value, (3, 3))
    tolerance = 1.0e-10
    expected_z = np.array([0.0, 0.0, 1.0])
    if not np.allclose(matrix[:, 2], expected_z, atol=tolerance, rtol=0.0):
        raise ValueError(f"{name} must leave the global Cartesian z axis unchanged.")
    if not np.allclose(matrix[2, :], expected_z, atol=tolerance, rtol=0.0):
        raise ValueError(f"{name} must leave the global Cartesian z axis unchanged.")
    determinant = float(np.linalg.det(matrix[:2, :2]))
    if not np.isfinite(determinant) or determinant <= 0.0:
        raise ValueError(f"{name} must preserve in-plane orientation.")
    return matrix


def _canonical_translation(translation_frac: Sequence[float]) -> tuple[float, float]:
    """Return a finite translation representative on the 2D fractional torus."""

    if len(translation_frac) != 2:
        raise ValueError(
            f"translation_frac must have length 2; got {len(translation_frac)}"
        )
    values = tuple(float(value) for value in translation_frac)
    if not all(np.isfinite(value) for value in values):
        raise ValueError("translation_frac must contain only finite values.")
    return (float(wrap01(values[0])), float(wrap01(values[1])))


def quantize_translation_frac(
    translation_frac: Sequence[float],
    round_decimals: int,
) -> tuple[float, float]:
    """Wrap and round a 2D fractional translation into a canonical representation.

    Rounding is followed by a second torus wrap so values rounded to exactly
    ``1.0`` return to ``0.0``. The result therefore always lies in ``[0, 1)``.
    """

    decimals = _nonnegative_integer("round_decimals", round_decimals)
    t1, t2 = _canonical_translation(translation_frac)
    return (
        float(wrap01(round(t1, decimals))),
        float(wrap01(round(t2, decimals))),
    )


def _embed_2x2_in_3x3(M2: Any, *, dtype: str = "float") -> np.ndarray:
    """Embed a finite 2x2 matrix into 3x3 with a fixed z-axis basis."""

    raw = np.asarray(M2)
    if raw.shape != (2, 2):
        raise ValueError(f"Expected 2x2 matrix; got shape {raw.shape}.")

    if dtype == "int":
        matrix = _exact_integer_matrix("M2", raw, (2, 2))
        out = np.eye(3, dtype=int)
    elif dtype == "float":
        matrix = _finite_matrix("M2", raw, (2, 2))
        out = np.eye(3, dtype=float)
    else:
        raise ValueError(f"dtype must be 'float' or 'int', got {dtype!r}")
    out[:2, :2] = matrix
    return out


# Geometry helpers are provided by calm.interface.building._geometry and are
# imported into this module for direct use. We intentionally do not re-wrap
# them here to avoid accidental recursion / name shadowing.


def _inplane_basis_rows(name: str, atoms: Any) -> np.ndarray:
    """Return and validate the first two row-cell vectors of an oriented slab."""

    cell = _bg._cell_array(atoms)
    if cell.shape != (3, 3) or not np.all(np.isfinite(cell)):
        raise ValueError(f"{name} cell must be a finite 3x3 matrix.")
    inplane = np.asarray(cell[:2], dtype=float)
    scale = float(np.max(np.abs(inplane)))
    if not np.isfinite(scale) or scale <= 0.0:
        raise ValueError(f"{name} in-plane cell must have a finite nonzero scale.")
    normalized = inplane / scale
    if not np.allclose(normalized[:, 2], 0.0, atol=1.0e-10, rtol=0.0):
        raise ValueError(f"{name} in-plane vectors must lie in the global xy plane.")
    determinant = float(np.linalg.det(normalized[:, :2]))
    if not np.isfinite(determinant) or determinant <= 1.0e-14:
        raise ValueError(f"{name} in-plane basis must be right-handed and nonsingular.")
    return inplane


def _common_inplane_error(basis_a: np.ndarray, basis_b: np.ndarray) -> float:
    """Return a scale-relative mismatch between two in-plane row bases."""

    scale = max(
        float(np.max(np.abs(basis_a))),
        float(np.max(np.abs(basis_b))),
    )
    if not np.isfinite(scale) or scale <= 0.0:
        raise ValueError("The common in-plane basis must have finite nonzero scale.")
    return float(np.max(np.abs(basis_a - basis_b)) / scale)


def _validate_positions(name: str, atoms: Any) -> None:
    """Require finite Cartesian positions before geometric placement."""

    positions = np.asarray(atoms.positions, dtype=float)
    if positions.ndim != 2 or positions.shape[1] != 3:
        raise ValueError(
            f"{name} positions must have shape (n, 3); got {positions.shape}."
        )
    if not np.all(np.isfinite(positions)):
        raise ValueError(f"{name} positions must contain only finite values.")


def _wrap_interface_positions(atoms: Any) -> None:
    """Wrap in-plane coordinates while preventing z-boundary slab splitting."""

    if not (
        hasattr(atoms, "get_scaled_positions")
        and hasattr(atoms, "set_scaled_positions")
    ):
        atoms.wrap()
        return

    from calm.structure.ase_adapter import wrap_xy_clamp_z

    wrap_xy_clamp_z(atoms)


def _validated_build_inputs(
    *,
    N_A3: Any,
    N_B3: Any,
    R_A3: Any,
    R_B3: Any,
    F_A: Any,
    F_B: Any,
    translation_frac: Sequence[float],
    z_padding: Any,
    vacuum_padding: Any,
) -> tuple[Any, ...]:
    """Validate and normalize the discrete and Cartesian build inputs."""

    shapes = tuple(np.asarray(value).shape for value in (N_A3, N_B3))
    if shapes != ((3, 3), (3, 3)):
        raise ValueError(f"Expected 3x3 N matrices; got {shapes[0]} and {shapes[1]}")
    shapes = tuple(np.asarray(value).shape for value in (R_A3, R_B3))
    if shapes != ((3, 3), (3, 3)):
        raise ValueError(f"Expected 3x3 R matrices; got {shapes[0]} and {shapes[1]}")
    shapes = tuple(np.asarray(value).shape for value in (F_A, F_B))
    if shapes != ((3, 3), (3, 3)):
        raise ValueError(
            "Expected 3x3 deformation-gradient matrices; got "
            f"{shapes[0]} and {shapes[1]}"
        )

    N_A3m = _validate_supercell_matrix("N_A3", N_A3)
    N_B3m = _validate_supercell_matrix("N_B3", N_B3)
    R_A3m = _validate_inplane_orthogonal_gauge("R_A3", R_A3)
    R_B3m = _validate_inplane_orthogonal_gauge("R_B3", R_B3)
    F_Am = _validate_inplane_deformation("F_A", F_A)
    F_Bm = _validate_inplane_deformation("F_B", F_B)
    t1, t2 = _canonical_translation(translation_frac)
    z_pad = _finite_nonnegative_float("z_padding", z_padding)
    z_vac = (
        z_pad
        if vacuum_padding is None
        else _finite_nonnegative_float("vacuum_padding", vacuum_padding)
    )
    return N_A3m, N_B3m, R_A3m, R_B3m, F_Am, F_Bm, t1, t2, z_pad, z_vac


def _transform_interface_slabs(
    slab_A_atoms: Any,
    slab_B_atoms: Any,
    inputs: tuple[Any, ...],
) -> tuple[Any, Any, float, float, float, float, InterfaceDeformationAccounting]:
    """Copy, supercell, rotate, and deform both input slabs."""

    N_A3m, N_B3m, R_A3m, R_B3m, F_Am, F_Bm, t1, t2, _, _ = inputs
    require_interface_stackable_slab(
        slab_A_atoms,
        name="Lower input slab",
    )
    require_interface_stackable_slab(
        slab_B_atoms,
        name="Upper input slab",
    )
    deformation_a = compose_slab_deformations(
        slab_A_atoms,
        F_Am,
        gauge_rotation=R_A3m,
        name="Lower input slab",
    )
    deformation_b = compose_slab_deformations(
        slab_B_atoms,
        F_Bm,
        gauge_rotation=R_B3m,
        name="Upper input slab",
    )

    from calm.structure.ase_adapter import make_supercell_col

    slab_a = make_supercell_col(slab_A_atoms.copy(), N_A3m)
    slab_b = make_supercell_col(slab_B_atoms.copy(), N_B3m)
    _bg._rotate_atoms_cartesian(slab_a, R_A3m)
    _bg._rotate_atoms_cartesian(slab_b, R_B3m)
    _bg._apply_deformation_gradient(slab_a, deformation_a.F_interface)
    _bg._apply_deformation_gradient(slab_b, deformation_b.F_interface)
    require_interface_ready_slab_cell(
        _bg._cell_array(slab_a),
        name="Transformed lower slab cell",
    )
    require_interface_ready_slab_cell(
        _bg._cell_array(slab_b),
        name="Transformed upper slab cell",
    )
    accounting = InterfaceDeformationAccounting(
        lower=deformation_a,
        upper=deformation_b,
    )
    return (
        slab_a,
        slab_b,
        float(t1),
        float(t2),
        float(inputs[8]),
        float(inputs[9]),
        accounting,
    )


def _common_interface_basis(slab_a: Any, slab_b: Any) -> tuple[np.ndarray, np.ndarray]:
    """Validate and return the common post-strain in-plane row basis."""

    _validate_positions("Lower slab", slab_a)
    _validate_positions("Upper slab", slab_b)
    basis_a = _inplane_basis_rows("Lower slab", slab_a)
    basis_b = _inplane_basis_rows("Upper slab", slab_b)
    common_error = _common_inplane_error(basis_a, basis_b)
    if common_error > 1.0e-10:
        raise ValueError(
            "The transformed slabs do not share one common in-plane basis; "
            f"relative mismatch={common_error:.3e}."
        )
    return basis_a[0].copy(), basis_a[1].copy()


def _place_slabs_along_z(
    slab_a: Any,
    slab_b: Any,
    *,
    z_padding: float,
    vacuum_padding: float,
) -> float:
    """Place both slabs and return the positive composite cell height."""

    z_a_min, z_a_max = _bg._zmin_zmax(slab_a)
    z_b_min, z_b_max = _bg._zmin_zmax(slab_b)
    height_a = float(z_a_max - z_a_min)
    height_b = float(z_b_max - z_b_min)
    heights = (height_a, height_b)
    if not all(np.isfinite(value) and value >= 0.0 for value in heights):
        raise ValueError("Slab thicknesses must be finite and non-negative.")

    slab_a.translate([0.0, 0.0, -z_a_min])
    _, shifted_a_max = _bg._zmin_zmax(slab_a)
    slab_b.translate([0.0, 0.0, shifted_a_max + z_padding - z_b_min])
    length_z = height_a + height_b + z_padding + vacuum_padding
    if not np.isfinite(length_z) or length_z <= 0.0:
        raise ValueError(
            "The constructed out-of-plane cell length must be finite and positive."
        )
    return float(length_z)


def prepare_interface_atoms(
    slab_A_atoms: Any,
    slab_B_atoms: Any,
    *,
    N_A3: np.ndarray,
    N_B3: np.ndarray,
    R_A3: np.ndarray,
    R_B3: np.ndarray,
    F_A: np.ndarray,
    F_B: np.ndarray,
    z_padding: float,
    vacuum_padding: float | None = None,
) -> PreparedInterfaceStructure:
    """Prepare translation-independent geometry for repeated interface builds."""

    inputs = _validated_build_inputs(
        N_A3=N_A3,
        N_B3=N_B3,
        R_A3=R_A3,
        R_B3=R_B3,
        F_A=F_A,
        F_B=F_B,
        translation_frac=(0.0, 0.0),
        z_padding=z_padding,
        vacuum_padding=vacuum_padding,
    )
    slab_a, slab_b, _, _, z_pad, z_vac, deformation_accounting = (
        _transform_interface_slabs(
            slab_A_atoms,
            slab_B_atoms,
            inputs,
        )
    )
    c1, c2 = _common_interface_basis(slab_a, slab_b)
    length_z = _place_slabs_along_z(
        slab_a,
        slab_b,
        z_padding=z_pad,
        vacuum_padding=z_vac,
    )

    composite_cell = np.vstack([c1, c2, [0.0, 0.0, length_z]])
    _bg._set_atoms_cell_no_scale(slab_a, composite_cell)
    _bg._set_atoms_cell_no_scale(slab_b, composite_cell)
    template_atoms = slab_a.copy()
    n_lower = len(template_atoms)
    template_atoms += slab_b
    template_atoms.pbc = (True, True, True)
    require_interface_ready_slab_cell(
        _bg._cell_array(template_atoms),
        name="Prepared interface cell",
    )
    lower_indices = np.arange(n_lower, dtype=int)
    upper_indices = np.arange(n_lower, len(template_atoms), dtype=int)
    c1_out = np.asarray(c1, dtype=float).copy()
    c2_out = np.asarray(c2, dtype=float).copy()
    for array in (lower_indices, upper_indices, c1_out, c2_out):
        array.setflags(write=False)
    return PreparedInterfaceStructure(
        template_atoms=template_atoms,
        lower_indices=lower_indices,
        upper_indices=upper_indices,
        c1=c1_out,
        c2=c2_out,
        Lz=float(length_z),
        deformation_accounting=deformation_accounting,
    )


def _materialize_prepared_interface_atoms(
    prepared: PreparedInterfaceStructure,
    *,
    translation_frac: tuple[float, float],
    copy_template: bool,
) -> BuiltInterfaceStructure:
    """Materialize one translation, optionally consuming an ephemeral template."""

    if not isinstance(prepared, PreparedInterfaceStructure):
        raise TypeError("prepared must be a PreparedInterfaceStructure.")
    t1, t2 = _canonical_translation(translation_frac)
    require_interface_ready_slab_cell(
        _bg._cell_array(prepared.template_atoms),
        name="Prepared interface template cell",
    )
    atoms = prepared.template_atoms.copy() if copy_template else prepared.template_atoms
    translation = t1 * prepared.c1 + t2 * prepared.c2
    atoms.positions[prepared.upper_indices] = (
        np.asarray(atoms.positions[prepared.upper_indices], dtype=float) + translation
    )
    _wrap_interface_positions(atoms)
    accounting = prepared.deformation_accounting
    if accounting is not None:
        info = getattr(atoms, "info", None)
        if info is None:
            try:
                setattr(atoms, "info", {})
            except (AttributeError, TypeError) as exc:
                raise TypeError(
                    "Built interface atoms must expose mutable info metadata."
                ) from exc
            info = getattr(atoms, "info", None)
        if not isinstance(info, MutableMapping):
            raise TypeError("Built interface atoms must expose mutable info metadata.")
        info[INTERFACE_DEFORMATION_ACCOUNTING_INFO_KEY] = (
            _deformation_accounting_payload(accounting)
        )

    return BuiltInterfaceStructure(
        atoms=atoms,
        lower_indices=np.asarray(prepared.lower_indices, dtype=int).copy(),
        upper_indices=np.asarray(prepared.upper_indices, dtype=int).copy(),
        c1=np.asarray(prepared.c1, dtype=float).copy(),
        c2=np.asarray(prepared.c2, dtype=float).copy(),
        Lz=float(prepared.Lz),
        deformation_accounting=prepared.deformation_accounting,
    )


def build_prepared_interface_atoms(
    prepared: PreparedInterfaceStructure,
    *,
    translation_frac: tuple[float, float],
) -> BuiltInterfaceStructure:
    """Build one translated interface from prepared invariant geometry."""

    return _materialize_prepared_interface_atoms(
        prepared,
        translation_frac=translation_frac,
        copy_template=True,
    )


def build_interface_atoms(
    slab_A_atoms: Any,
    slab_B_atoms: Any,
    *,
    N_A3: np.ndarray,
    N_B3: np.ndarray,
    R_A3: np.ndarray,
    R_B3: np.ndarray,
    F_A: np.ndarray,
    F_B: np.ndarray,
    translation_frac: tuple[float, float],
    z_padding: float,
    vacuum_padding: float | None = None,
) -> BuiltInterfaceStructure:
    """Build one deterministic periodic interface from two oriented slabs."""

    prepared = prepare_interface_atoms(
        slab_A_atoms,
        slab_B_atoms,
        N_A3=N_A3,
        N_B3=N_B3,
        R_A3=R_A3,
        R_B3=R_B3,
        F_A=F_A,
        F_B=F_B,
        z_padding=z_padding,
        vacuum_padding=vacuum_padding,
    )
    return _materialize_prepared_interface_atoms(
        prepared,
        translation_frac=translation_frac,
        copy_template=False,
    )
