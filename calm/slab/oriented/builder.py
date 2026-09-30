"""Construct oriented slab cells with explicit transformation provenance.

The primary path starts from the primitive bulk cell and composes distinct
classes of operations:

1. exact integer supercell and lattice-basis transformations;
2. proper Cartesian rotations that establish the slab frame;
3. optional bounded integer gauge choices for in-plane and c-tilt reduction;
4. an optional physical shear that orthogonalizes the stacking vector;
5. an orientation-preserving sign gauge; and
6. optional Cartesian-z vacuum padding with a representation-only orthogonal
   vacuum vector.

The transform bundle records which operations change the lattice basis, which
change the Cartesian frame, and which are physical deformations.  Vacuum and
wrapping are representation operations and are not included in the physical
Cartesian frame map.

Conventions
-----------
ASE stores lattice vectors as rows in ``C = atoms.cell.array``.  CALM's exact
integer algebra uses lattice vectors as columns in ``A = C.T``.  Therefore a
column-basis transform ``A' = A @ S`` appears in ASE storage as
``C' = S.T @ C``.  A Cartesian map ``x' = M @ x`` acts on row-position arrays
as ``X' = X @ M.T``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np

from calm.structure.ase_adapter import make_supercell_col, supercell_matrix_ase_from_col
from calm.serialization.scientific import scientific_json_native as _json_native
from calm.slab.oriented._primitive import (
    DEFAULT_PRIMITIVE_MAX_DENOMINATOR,
    DEFAULT_PRIMITIVE_REDUCTION_MAX_ITER,
    DEFAULT_STACKING_SEARCH_RADIUS,
    compute_primitive_surface_basis,
)
from calm.slab.oriented.cell_contract import (
    INTERFACE_READY_SLAB_CELL_POLICY,
    INTERFACE_READY_SLAB_CELL_POLICY_VERSION,
    assess_oriented_surface_cell,
    require_interface_ready_slab_cell,
)
from calm.slab.oriented._lattice import (
    DEFAULT_C_TILT_SEARCH_RADIUS,
    DEFAULT_C_TILT_SINGULAR_TOLERANCE,
    _c_orthogonalization_from_cell,
    _c_tilt_reduction_matrix,
    _compute_R_from_ab_to_xy,
    _compute_R_from_normal_and_inplane,
    _embed_u2_into_u3,
    _nonnegative_finite_float,
    _normal_sign,
    _positive_finite_float,
    _positive_integer,
    _reduce_hkl,
    _to_int_mat,
    surface_basis_S_from_hkl,
)
from calm.slab.oriented.transforms import (
    bounded_surface_gauge_controls,
    canonical_construction_controls,
)

if TYPE_CHECKING:
    from calm.bulk.bulk import Bulk

try:
    from ase import Atoms
    from ase.build import make_supercell
except ImportError:  # pragma: no cover - exercised without the science extra
    Atoms = Any  # type: ignore[misc,assignment]
    make_supercell = None  # type: ignore[assignment]


ArrayF = np.ndarray
ArrayI = np.ndarray


def _apply_cartesian_rotation(atoms: Atoms, R: ArrayF) -> Atoms:
    """Apply a pure rotation to an ASE Atoms (row-storage compatible)."""

    R = np.asarray(R, dtype=float)
    if R.shape != (3, 3):
        raise ValueError("R must be (3,3).")

    out = atoms.copy()
    out.set_cell(out.cell.array @ R.T, scale_atoms=False)
    out.set_positions(out.positions @ R.T)
    out.wrap(eps=1e-5)
    return out


def _orient_block_to_slab_frame(
    pre_oriented: Atoms,
    *,
    normal_sign: int = +1,
    ortho_tol: float = 1e-10,
) -> tuple[Atoms, ArrayF]:
    """Rotate a periodic block so its first two cell vectors lie in ``xy``."""
    a_initial, b_initial, _ = pre_oriented.cell.array
    rotation = _compute_R_from_ab_to_xy(
        a_initial,
        b_initial,
        normal_sign=normal_sign,
        ortho_tol=ortho_tol,
    )
    oriented = _apply_cartesian_rotation(pre_oriented, rotation)
    tolerance = _nonnegative_finite_float("ortho_tol", ortho_tol)
    for name, vector in zip(("a", "b"), oriented.cell.array[:2], strict=True):
        norm = float(np.linalg.norm(vector))
        if norm <= 0.0 or abs(float(vector[2])) > tolerance * norm:
            raise RuntimeError(
                "Orientation constraint failed: "
                f"{name}_z={vector[2]:.3e}, norm={norm:.3e}, "
                f"relative_tol={tolerance:.3e}."
            )
    return oriented, rotation


def _clamp_fractional_coords(
    atoms: Atoms,
    *,
    tol: float = 1e-10,
    decimals: int = 12,
) -> None:
    """Clamp wrapped fractional coordinates at periodic boundaries."""
    fractional = np.asarray(
        atoms.get_scaled_positions(wrap=False),
        dtype=float,
    )
    fractional = np.around(fractional, decimals=decimals)
    fractional[np.abs(fractional) < tol] = 0.0
    fractional[np.abs(fractional - 1.0) < tol] = 1.0 - tol
    fractional = np.clip(fractional, 0.0, 1.0 - tol)
    atoms.positions[:] = fractional @ atoms.get_cell()


def _finalize_wrap_and_clamp(
    block: Atoms,
    slab: Atoms,
    *,
    wrap: bool = True,
) -> tuple[Atoms, Atoms]:
    """Wrap and stabilize fractional coordinates before returning results."""
    if not wrap:
        return block, slab

    block.wrap(eps=1e-5)
    _clamp_fractional_coords(block)
    if slab is not block:
        slab.wrap(eps=1e-5)
        _clamp_fractional_coords(slab)
    return block, slab


def _construct_transforms(
    hkl_red: tuple[int, int, int],
    layers: int,
    S_layers: ArrayF,
    U_inplane: ArrayF | None,
    P_row_used: ArrayF,
    R_conv_to_slab_total: ArrayF,
    R_align: ArrayF | None,
    L_c_tilt_row: ArrayF | None,
    mn: tuple[int, int] | None,
    shear_info: dict[str, Any] | None,
    vacuum_info: dict[str, Any] | None,
    canonical_fix: dict[str, Any] | None,
    construction_controls: dict[str, Any],
    supercell_reference: str = "conventional",
    miller_primitive: tuple[int, int, int] | None = None,
) -> OrientedSlabTransforms:
    """Construct a complete oriented-slab provenance bundle.

    Provenance construction is part of the slab-construction contract.  Invalid
    transform data therefore raises at the construction boundary rather than
    being converted into a delayed ``None`` failure.
    """
    return OrientedSlabTransforms(
        hkl_reduced=hkl_red,
        layers=int(layers),
        S_conv_to_surface_col=S_layers,
        U_inplane_col=U_inplane,
        P_supercell_row=P_row_used,
        R_conv_to_slab=R_conv_to_slab_total,
        R_slab_to_conv=R_conv_to_slab_total.T,
        R_align=R_align,
        L_c_tilt_row=L_c_tilt_row,
        c_tilt_mn=mn,
        shear_info=shear_info,
        vacuum_info=vacuum_info,
        canonical_sign_fix=canonical_fix,
        construction_controls=construction_controls,
        supercell_reference=supercell_reference,
        miller_primitive=miller_primitive,
    )


def _apply_canonical_sign_fix(slab: Atoms) -> dict[str, Any] | None:
    """Apply a deterministic orientation-preserving diagonal basis gauge."""
    cell = np.asarray(slab.cell.array, dtype=float)
    if cell.shape != (3, 3) or not np.all(np.isfinite(cell)):
        raise ValueError("slab cell must be a finite 3x3 matrix")
    determinant = float(np.linalg.det(cell))
    if abs(determinant) <= np.finfo(float).tiny:
        raise ValueError("slab cell must be nonsingular")
    if determinant < 0.0:
        raise ValueError(
            "slab cell must be right-handed before the canonical sign gauge"
        )

    signs = np.array(
        [
            1 if cell[0, 0] >= 0.0 else -1,
            1 if cell[1, 1] >= 0.0 else -1,
            1 if cell[2, 2] >= 0.0 else -1,
        ],
        dtype=int,
    )
    diagonal = np.diag(signs)
    if int(round(np.linalg.det(diagonal))) < 0:
        # Preserve a right-handed basis.  In the one- or three-negative-axis
        # cases not every selected diagonal component can be made positive by
        # an orientation-preserving diagonal gauge; retain the x and z choices
        # and use y as the deterministic parity correction.
        diagonal[1, 1] *= -1
    if np.array_equal(diagonal, np.eye(3, dtype=int)):
        return None

    scaled_old = np.asarray(slab.get_scaled_positions(wrap=False), dtype=float)
    slab.set_cell(diagonal @ cell, scale_atoms=False)
    slab.set_scaled_positions(scaled_old @ diagonal.T)
    slab.wrap(eps=1e-5)
    return {"L_diag": diagonal.tolist()}


def _proper_inplane_reduction_pair(
    transform_2d: np.ndarray,
    rotation_2d: np.ndarray,
    *,
    tolerance: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Return an orientation-preserving representative of a 2D reduction.

    ``canonical_gauss_reduce_2d`` may encode its final canonical sign choice as a
    paired reflection: both the integer basis transform and the orthogonal
    embedding then have determinant ``-1``.  Their product is still a valid
    right-handed reduced basis, but neither factor can be recorded as an
    orientation-preserving 3D slab operation.

    Flipping the first reduced basis coordinate in both factors replaces that
    paired reflection by an equivalent ``SL(2,Z)`` transform and proper
    rotation.  Reduced vector lengths, area, and the absolute inner product
    are unchanged; only the sign of the off-diagonal metric component changes.
    """
    transform = _to_int_mat(transform_2d, name="U2")
    rotation = np.asarray(rotation_2d, dtype=float)
    if rotation.shape != (2, 2):
        raise ValueError(f"R2 must have shape (2,2), got {rotation.shape}")

    determinant = int(round(np.linalg.det(transform)))
    if abs(determinant) != 1:
        raise RuntimeError(
            f"Expected a unimodular 2D reduction; det(U2)={determinant}."
        )

    if not np.allclose(
        rotation.T @ rotation,
        np.eye(2),
        atol=tolerance,
        rtol=0.0,
    ):
        raise RuntimeError("2D reduction returned a nonorthogonal gauge map")
    rotation_determinant = float(np.linalg.det(rotation))
    if not np.isclose(
        abs(rotation_determinant),
        1.0,
        atol=tolerance,
        rtol=0.0,
    ):
        raise RuntimeError(
            "2D reduction returned a singular gauge map; "
            f"det(R2)={rotation_determinant:.16g}."
        )
    rotation_sign = 1 if rotation_determinant > 0.0 else -1
    if determinant != rotation_sign:
        raise RuntimeError(
            "2D reduction returned inconsistent orientation factors: "
            f"det(U2)={determinant}, det(R2)={rotation_determinant:.16g}."
        )

    if determinant == -1:
        reflection = np.diag([-1, 1])
        transform = transform @ reflection.astype(int)
        rotation = reflection @ rotation

    if int(round(np.linalg.det(transform))) != 1:
        raise RuntimeError("Failed to construct an orientation-preserving U2")
    if not np.isclose(
        np.linalg.det(rotation),
        1.0,
        atol=tolerance,
        rtol=0.0,
    ):
        raise RuntimeError("Failed to construct a proper in-plane rotation")
    return transform, rotation


def _normalized_inplane_reduction_frame(
    vector_a: np.ndarray,
    vector_b: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return a scale-normalized slab frame and 2D in-plane basis."""
    vector_a = np.asarray(vector_a, dtype=float)
    vector_b = np.asarray(vector_b, dtype=float)
    if vector_a.shape != (3,) or vector_b.shape != (3,):
        raise ValueError("In-plane vectors must each have shape (3,)")

    vector_scale = float(max(np.max(np.abs(vector_a)), np.max(np.abs(vector_b))))
    if not np.isfinite(vector_scale) or vector_scale <= 0.0:
        raise ValueError("In-plane basis must have a finite, nonzero scale")

    scaled_a = vector_a / vector_scale
    scaled_b = vector_b / vector_scale
    a_norm = float(np.linalg.norm(scaled_a))
    normal = np.cross(scaled_a, scaled_b)
    normal_norm = float(np.linalg.norm(normal))
    if a_norm <= 0.0 or normal_norm <= 0.0:
        raise ValueError("Degenerate in-plane basis: a and b must be independent")

    first_axis = scaled_a / a_norm
    third_axis = normal / normal_norm
    second_axis = np.cross(third_axis, first_axis)
    plane_axes = np.vstack([first_axis, second_axis])
    basis_2d = plane_axes @ np.column_stack([scaled_a, scaled_b])
    basis_scale = float(np.max(np.abs(basis_2d)))
    if not np.isfinite(basis_scale) or basis_scale <= 0.0:
        raise ValueError("In-plane basis must have a finite, nonzero scale")

    return (
        first_axis,
        second_axis,
        third_axis,
        basis_2d / basis_scale,
    )


def _reduce_inplane_by_metric(
    atoms: Atoms,
    *,
    symprec: float = 1e-5,
) -> tuple[Atoms, np.ndarray, np.ndarray]:
    """Apply a scale-invariant 2D lattice reduction and gauge rotation.

    The returned matrices satisfy two distinct roles:

    ``U3``
        An integer column-basis change.  In ASE row convention the cell change
        is ``C_lattice = U3.T @ C`` and Cartesian positions are preserved.

    ``R3``
        A proper Cartesian rotation applied after the basis change.  For an
        already oriented slab it acts only in the surface plane and places the
        reduced first vector on the positive x axis.
    """
    from calm.symmetry.reduction import canonical_gauss_reduce_2d

    tolerance = _nonnegative_finite_float("symprec", symprec)
    a = np.asarray(atoms.cell.array[0], dtype=float)
    b = np.asarray(atoms.cell.array[1], dtype=float)
    e1, e2, e3, basis_2d = _normalized_inplane_reduction_frame(a, b)

    _, transform_2d, rotation_2d = canonical_gauss_reduce_2d(
        basis_2d,
        tol=tolerance,
    )
    transform_2d_int, rotation_2d = _proper_inplane_reduction_pair(
        transform_2d,
        rotation_2d,
        tolerance=tolerance,
    )
    transform_3d = _embed_u2_into_u3(transform_2d_int)

    out = atoms.copy()
    row_transform = transform_3d.T
    scaled_old = np.asarray(out.get_scaled_positions(wrap=False), dtype=float)
    row_inverse = np.linalg.inv(row_transform.astype(float))
    row_inverse_int = np.rint(row_inverse).astype(int)
    if not np.allclose(row_inverse, row_inverse_int, atol=1e-12, rtol=0.0):
        raise RuntimeError("Expected the in-plane basis transform to be unimodular")
    out.set_cell(row_transform @ out.cell.array, scale_atoms=False)
    out.set_scaled_positions(scaled_old @ row_inverse_int)

    rotation_2d = np.asarray(rotation_2d, dtype=float)
    if not np.allclose(
        rotation_2d.T @ rotation_2d,
        np.eye(2),
        atol=tolerance,
        rtol=0.0,
    ) or not np.isclose(
        np.linalg.det(rotation_2d),
        1.0,
        atol=tolerance,
        rtol=0.0,
    ):
        raise RuntimeError("2D reduction returned an improper gauge rotation")

    frame = np.column_stack([e1, e2, e3])
    rotation_local = np.eye(3, dtype=float)
    rotation_local[:2, :2] = rotation_2d
    rotation_3d = frame @ rotation_local @ frame.T
    out = _apply_cartesian_rotation(out, rotation_3d)
    out.wrap(eps=1e-5)
    return out, transform_3d, rotation_3d


def _reduce_c_tilt_integer(
    atoms: Atoms,
    *,
    search: int = DEFAULT_C_TILT_SEARCH_RADIUS,
    singular_tol: float = DEFAULT_C_TILT_SINGULAR_TOLERANCE,
) -> tuple[Atoms, tuple[int, int], ArrayF]:
    """Apply the bounded integer gauge ``c <- c + m a + n b``."""
    pair, row_transform = _c_tilt_reduction_matrix(
        np.asarray(atoms.cell.array, dtype=float),
        search=search,
        singular_tol=singular_tol,
    )
    out = atoms.copy()
    scaled_old = np.asarray(out.get_scaled_positions(wrap=False), dtype=float)
    row_inverse = np.linalg.inv(row_transform.astype(float))
    row_inverse_int = np.rint(row_inverse).astype(int)
    if not np.allclose(row_inverse, row_inverse_int, atol=1e-12, rtol=0.0):
        raise RuntimeError("Expected c-tilt transform to be unimodular integer")
    out.set_cell(row_transform @ out.cell.array, scale_atoms=False)
    out.set_scaled_positions(scaled_old @ row_inverse_int)
    out.wrap(eps=1e-5)
    return out, pair, row_transform


def _orthogonalize_c_by_shear(
    atoms: Atoms,
    *,
    z_axis: int = 2,
    z_tol: float = 1e-10,
) -> tuple[Atoms, dict[str, Any]]:
    """Apply a volume-preserving physical shear that removes c tilt."""
    cell_old = np.asarray(atoms.cell.array, dtype=float)
    cell_new, lattice_shear, deformation, alpha, beta = _c_orthogonalization_from_cell(
        cell_old,
        z_axis=z_axis,
        z_tol=z_tol,
    )
    out = atoms.copy()
    out.set_cell(cell_new, scale_atoms=True)
    out.wrap(eps=1e-5)
    inplane_axes = [axis for axis in range(3) if axis != z_axis]
    return out, {
        "alpha": alpha,
        "beta": beta,
        "U_shear_lattice": lattice_shear,
        "F_shear_cart": deformation,
        "c_xy_norm_before": float(np.linalg.norm(cell_old[2, inplane_axes])),
        "c_xy_norm_after": float(np.linalg.norm(out.cell.array[2, inplane_axes])),
    }


def _unwrap_to_largest_z_gap(
    atoms: Atoms,
    *,
    z_axis: int = 2,
    tol: float = 1e-12,
) -> tuple[Atoms, float]:
    """Choose the periodic image whose largest atomic z gap is the boundary."""
    if z_axis not in (0, 1, 2):
        raise ValueError("z_axis must be 0, 1, or 2")
    tolerance = _nonnegative_finite_float("tol", tol)
    out = atoms.copy()
    if len(out) == 0:
        raise ValueError("Cannot unwrap an empty structure")
    cell = np.asarray(out.cell.array, dtype=float)
    c_vector = cell[2]
    period = abs(float(c_vector[z_axis]))
    scale = float(np.linalg.norm(c_vector))
    if scale <= 0.0 or period <= tolerance * scale:
        raise RuntimeError(
            "Cell has an insufficient Cartesian-z period for unwrapping; "
            f"period={period:.3e}, |c|={scale:.3e}."
        )

    z_mod = np.mod(np.asarray(out.positions[:, z_axis], dtype=float), period)
    z_sorted = np.sort(z_mod)
    extended = np.concatenate([z_sorted, [z_sorted[0] + period]])
    gaps = np.diff(extended)
    largest_gap_index = int(np.argmax(gaps))
    left = float(z_sorted[largest_gap_index])
    right = float(extended[largest_gap_index + 1])
    boundary = float(0.5 * (left + right) % period)
    shift = np.zeros(3, dtype=float)
    shift[z_axis] = -boundary
    out.translate(shift)
    out.wrap(eps=1e-5)
    return out, boundary


def _add_vacuum_along_cartesian_z(
    atoms: Atoms,
    vacuum: float,
    *,
    center: bool = True,
    unwrap_first: bool = True,
    z_axis: int = 2,
    z_tol: float = 1e-10,
) -> tuple[Atoms, dict[str, Any]]:
    """Add Cartesian-z vacuum and use an orthogonal boundary vector.

    The incoming periodic bulk block may carry an irreducible in-plane
    stacking translation in its third lattice vector.  Once a positive vacuum
    region is introduced, that lateral image shift is no longer part of the
    finite slab geometry.  CALM therefore sets the boundary vector parallel to
    the selected Cartesian z axis without scaling or shearing the atomic
    geometry.  Subsequent wrapping may select equivalent in-plane periodic
    images.  This is a representation change, not the optional physical shear
    implemented by :func:`_orthogonalize_c_by_shear`.
    """
    padding = _nonnegative_finite_float("vacuum", vacuum)
    alignment_tolerance = _nonnegative_finite_float("z_tol", z_tol)
    if z_axis not in (0, 1, 2):
        raise ValueError("z_axis must be 0, 1, or 2")

    out = atoms.copy()
    if len(out) == 0:
        raise ValueError("Cannot add vacuum to an empty structure")
    cell_initial = np.asarray(out.cell.array, dtype=float)
    if z_axis != 2:
        raise ValueError(
            "Current interface-ready slab policy requires global Cartesian z."
        )
    periodic_assessment = assess_oriented_surface_cell(
        cell_initial,
        name="Periodic slab block cell",
    )

    boundary_shift = 0.0
    if unwrap_first:
        out, boundary_shift = _unwrap_to_largest_z_gap(
            out,
            z_axis=z_axis,
            tol=z_tol,
        )

    cell = np.asarray(out.cell.array, dtype=float)
    c_vector = cell[2].copy()
    c_component = float(c_vector[z_axis])
    sign = 1.0 if c_component >= 0.0 else -1.0
    old_period = abs(c_component)
    c_norm = float(np.linalg.norm(c_vector))
    if c_norm <= 0.0 or old_period <= alignment_tolerance * c_norm:
        raise RuntimeError("Cannot add vacuum: c has insufficient z component")

    z_mod = np.mod(
        np.asarray(out.positions[:, z_axis], dtype=float),
        old_period,
    )
    z_min = float(np.min(z_mod))
    z_max = float(np.max(z_mod))
    thickness = z_max - z_min
    new_period = thickness + 2.0 * padding
    if new_period <= 0.0:
        # A one-plane structure with zero requested padding would otherwise
        # create a singular cell.  The public builders skip zero-padding calls,
        # but retain a direct-helper guard for completeness.
        raise ValueError("Vacuum insertion requires positive final z extent")

    inplane_axes = [axis for axis in range(3) if axis != z_axis]
    c_inplane_before = np.asarray(cell[2, inplane_axes], dtype=float).copy()

    cell_new = cell.copy()
    cell_new[2, inplane_axes] = 0.0
    cell_new[2, z_axis] = sign * new_period
    out.set_cell(cell_new, scale_atoms=False)

    translation = 0.0
    if center:
        translation = padding - z_min
        shift = np.zeros(3, dtype=float)
        shift[z_axis] = translation
        out.translate(shift)
    out.wrap(eps=1e-5)

    interface_assessment = require_interface_ready_slab_cell(
        out.cell.array,
        name="Vacuum slab cell",
    )

    c_inplane_after = np.asarray(
        out.cell.array[2, inplane_axes],
        dtype=float,
    )
    return out, {
        "vacuum_per_side": padding,
        "center": bool(center),
        "unwrap_first": bool(unwrap_first),
        "unwrap_boundary_shift_z": float(boundary_shift),
        "Lz_old": float(old_period),
        "Lz_new": float(new_period),
        "slab_thickness_z": float(thickness),
        "translation_applied_z": float(translation),
        "c_inplane_before": c_inplane_before.tolist(),
        "c_inplane_after": c_inplane_after.tolist(),
        "c_xy_norm_before": float(np.linalg.norm(c_inplane_before)),
        "c_xy_norm_after": float(np.linalg.norm(c_inplane_after)),
        "c_xy_norm": float(np.linalg.norm(c_inplane_after)),
        "orthogonal_vacuum_axis": True,
        "cell_policy": INTERFACE_READY_SLAB_CELL_POLICY,
        "cell_policy_version": INTERFACE_READY_SLAB_CELL_POLICY_VERSION,
        "canonicalization_mode": (
            "already_orthogonal"
            if periodic_assessment.interface_ready
            else "boundary_reembedding"
        ),
        "canonicalization_applies_physical_strain": False,
        "interface_ready": interface_assessment.interface_ready,
    }


@dataclass(frozen=True)
class OrientedSlabTransforms:
    """Transformation provenance for an oriented slab."""

    hkl_reduced: tuple[int, int, int]
    layers: int

    # Lattice-level transforms
    S_conv_to_surface_col: ArrayF  # (3,3) int, det = layers

    # 3x3 unimodular in-plane metric reduction (column convention).
    #
    # We intentionally store an explicit matrix (identity if no-op) so that
    # transformation provenance is always complete/auditable and JSON
    # round-trips don't depend on implicit defaults.
    U_inplane_col: ArrayF | None  # (3,3) int, det=+1

    # ASE row convention supercell matrix (for make_supercell)
    P_supercell_row: ArrayF  # (3,3) int

    # Cartesian rotations
    R_conv_to_slab: ArrayF  # (3,3) float
    R_slab_to_conv: ArrayF  # (3,3) float

    # Gauge fixing rotation from canonical 2D Gauss reduction
    #
    # This rotation is applied during canonical 2D Gauss reduction to align the first
    # in-plane lattice vector with the +x axis (canonical gauge). It is a pure
    # Cartesian rotation in the surface plane.
    #
    # If reduce_inplane=False, this is None (or identity after __post_init__).
    R_align: ArrayF | None  # (3,3) float, orthogonal

    # Optional integer c-tilt reduction (row convention)
    L_c_tilt_row: ArrayF | None  # (3,3) int
    c_tilt_mn: tuple[int, int] | None

    # Optional physical shear used to orthogonalize c
    shear_info: dict[str, Any] | None

    # Optional vacuum info (non-physical)
    vacuum_info: dict[str, Any] | None

    # Complete versioned bounds and numerical controls used by canonical
    # construction. Current kernel provenance never omits them.
    construction_controls: dict[str, Any]

    # Explicit canonical sign-fix provenance recorded when final gauge fixes
    # required flipping of cell axes to maintain positive-axis convention.
    canonical_sign_fix: dict[str, Any] | None = None

    # Basis to which ``P_supercell_row`` applies.
    supercell_reference: str = "conventional"

    # Primitive-coordinate Miller covector used by the primary exact path.
    miller_primitive: tuple[int, int, int] | None = None

    @property
    def F_ideal_to_slab(self) -> ArrayF:
        """Return the physical map from the pre-shear to final slab frame.

        The map is identity when ``orthogonalize_c`` was not requested.  When
        orthogonalization was requested, Cartesian vectors obey
        ``x_slab = F_ideal_to_slab @ x_ideal``.
        """
        deformation = self.F_orthogonalize_c_slab
        if deformation is None:
            return np.eye(3, dtype=float)
        return deformation

    @property
    def F_slab_to_ideal(self) -> ArrayF:
        """Return the inverse physical map from final slab to pre-shear frame."""
        return np.linalg.inv(self.F_ideal_to_slab)

    def __post_init__(self) -> None:
        """Normalize optional transforms to explicit identity matrices.

        For transformation provenance, it is preferable to record explicit
        unimodular/orthogonal matrices even when they are the identity. This
        simplifies downstream composition (chain multiplication) and avoids
        `None` handling in serialization/round-trip tests.
        """

        if self.U_inplane_col is None:
            object.__setattr__(self, "U_inplane_col", np.eye(3, dtype=int))

        if self.R_align is None:
            object.__setattr__(self, "R_align", np.eye(3, dtype=float))

        reference = str(self.supercell_reference)
        if reference not in {"conventional", "primitive"}:
            raise ValueError(
                "supercell_reference must be 'conventional' or 'primitive'"
            )
        object.__setattr__(self, "supercell_reference", reference)
        if self.miller_primitive is not None:
            object.__setattr__(
                self,
                "miller_primitive",
                _reduce_hkl(self.miller_primitive),
            )
        object.__setattr__(
            self,
            "construction_controls",
            canonical_construction_controls(self.construction_controls),
        )

    def to_dict(self) -> dict[str, Any]:
        def _arr(a: ArrayF | None) -> Any:
            if a is None:
                return None
            return np.asarray(a).tolist()

        return {
            "hkl_reduced": list(self.hkl_reduced),
            "layers": int(self.layers),
            "S_conv_to_surface_col": _arr(self.S_conv_to_surface_col),
            "U_inplane_col": _arr(self.U_inplane_col),
            "P_supercell_row": _arr(self.P_supercell_row),
            "R_conv_to_slab": _arr(self.R_conv_to_slab),
            "R_slab_to_conv": _arr(self.R_slab_to_conv),
            "R_align": _arr(self.R_align),
            "L_c_tilt_row": _arr(self.L_c_tilt_row),
            "c_tilt_mn": None if self.c_tilt_mn is None else list(self.c_tilt_mn),
            "shear_info": _json_native(self.shear_info),
            "vacuum_info": _json_native(self.vacuum_info),
            "canonical_sign_fix": _json_native(self.canonical_sign_fix),
            "supercell_reference": self.supercell_reference,
            "miller_primitive": (
                None if self.miller_primitive is None else list(self.miller_primitive)
            ),
            "construction_controls": _json_native(self.construction_controls),
        }

    def to_json(self, *, sort_keys: bool = True, indent: int | None = None) -> str:
        """Serialize this transform bundle as a JSON string."""
        return json.dumps(self.to_dict(), sort_keys=sort_keys, indent=indent)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "OrientedSlabTransforms":
        """Reconstruct transforms from :meth:`to_dict` output."""
        # Required keys
        hkl_reduced = tuple(int(x) for x in d["hkl_reduced"])
        layers = int(d["layers"])

        def _arr(key: str, *, dtype: type = float) -> np.ndarray:
            return np.asarray(d[key], dtype=dtype)

        def _arr_opt(key: str, *, dtype: type = float) -> np.ndarray | None:
            v = d.get(key, None)
            if v is None:
                return None
            return np.asarray(v, dtype=dtype)

        c_tilt_mn = d.get("c_tilt_mn", None)
        if c_tilt_mn is not None:
            c_tilt_mn = tuple(int(x) for x in c_tilt_mn)

        return cls(
            hkl_reduced=hkl_reduced,
            layers=layers,
            S_conv_to_surface_col=_arr("S_conv_to_surface_col", dtype=float),
            U_inplane_col=_arr_opt("U_inplane_col", dtype=float),
            P_supercell_row=_arr("P_supercell_row", dtype=float),
            R_conv_to_slab=_arr("R_conv_to_slab", dtype=float),
            R_slab_to_conv=_arr("R_slab_to_conv", dtype=float),
            R_align=_arr_opt("R_align", dtype=float),
            L_c_tilt_row=_arr_opt("L_c_tilt_row", dtype=float),
            c_tilt_mn=c_tilt_mn,
            shear_info=d.get("shear_info", None),
            vacuum_info=d.get("vacuum_info", None),
            canonical_sign_fix=d.get("canonical_sign_fix", None),
            supercell_reference=str(d.get("supercell_reference", "conventional")),
            miller_primitive=(
                None
                if d.get("miller_primitive") is None
                else tuple(int(x) for x in d["miller_primitive"])
            ),
            construction_controls=d["construction_controls"],
        )

    @classmethod
    def from_json(cls, s: str) -> "OrientedSlabTransforms":
        """Reconstruct transforms from :meth:`to_json` output."""
        return cls.from_dict(json.loads(s))

    @property
    def F_orthogonalize_c_slab(self) -> ArrayF | None:
        """Return the Cartesian shear used to remove residual c-tilt.

        When :pyparamref:`build_oriented_slab.orthogonalize_c`
        is True, we apply a pure shear so that the slab cell has ``c_xy == 0``
        (i.e., *c* is normal to the *a-b* plane). This property exposes that
        deformation gradient for downstream strain provenance.
        """
        if self.shear_info is None:
            return None
        F = self.shear_info.get("F_shear_cart")
        if F is None:
            return None
        return np.asarray(F, dtype=float)

    def M_conv_to_slab_cart(self) -> np.ndarray:
        """Return the Cartesian-frame mapping from conventional -> slab.

        This matrix ``M`` is defined such that a Cartesian vector expressed in the
        conventional-cell frame is mapped into the (possibly shear-orthogonalized)
        slab Cartesian frame by::

            x_slab = M @ x_conv

        Notes
        -----
        - Integer supercell / unimodular basis operations used during slab construction
          are *not* physical strains and do not appear here.
        - If ``orthogonalize_c`` was applied, this mapping includes the associated
          shear deformation gradient.
        """
        M = np.asarray(self.R_conv_to_slab, dtype=float)
        F_shear = self.F_orthogonalize_c_slab
        if F_shear is not None:
            M = np.asarray(F_shear, dtype=float) @ M
        return M

    def M_slab_to_conv_cart(self) -> np.ndarray:
        """Return the inverse Cartesian-frame mapping from slab -> conventional.

        This is the inverse of :meth:`M_conv_to_slab_cart`, i.e.::

            x_conv = M_inv @ x_slab
        """
        M = np.asarray(self.R_slab_to_conv, dtype=float)
        F_shear = self.F_orthogonalize_c_slab
        if F_shear is not None:
            M = M @ np.linalg.inv(np.asarray(F_shear, dtype=float))
        return M

    def R_conv_to_ungauged(self) -> np.ndarray:
        """Rotation from conventional to ungauged slab frame.

        This returns the rotation that would be measured if canonical 2D Gauss reduction
        had NOT been applied with gauge fixing. It represents the "pure"
        orientation change from conventional to slab without the canonical
        gauge alignment.

        Returns
        -------
        R : (3,3) ndarray
            Orthogonal rotation matrix.

        Notes
        -----
        If ``reduce_inplane`` was False (no canonical 2D Gauss reduction), this is
        identical to ``R_conv_to_slab``.

        The stored ``R_conv_to_slab`` is the total rotation that includes
        gauge fixing. To decompose:

            R_conv_to_slab = R_align @ R_conv_to_ungauged

        Therefore:

            R_conv_to_ungauged = R_align.T @ R_conv_to_slab
        """
        R_align = self.R_align
        if R_align is None or np.allclose(R_align, np.eye(3), atol=1e-10):
            return np.asarray(self.R_conv_to_slab, dtype=float)

        # Decompose: R_conv_to_slab = R_align @ R_conv_to_ungauged
        # So: R_conv_to_ungauged = R_align.T @ R_conv_to_slab
        R_align = np.asarray(R_align, dtype=float)
        R_total = np.asarray(self.R_conv_to_slab, dtype=float)
        return R_align.T @ R_total


@dataclass(frozen=True)
class OrientedSlabResult:
    """Result of oriented slab construction."""

    # Fully periodic block (no vacuum) in slab frame.
    block: Atoms

    # If vacuum was requested, ``slab`` is the vacuum-padded variant; else it is
    # identical to ``block``.
    slab: Atoms

    transforms: OrientedSlabTransforms

    @property
    def hkl_reduced(self) -> tuple[int, int, int]:
        """Miller index used for the surface (reduced / primitive form)."""
        return self.transforms.hkl_reduced

    @property
    def layers(self) -> int:
        """Number of layers (repeat count) along the surface normal."""
        return int(self.transforms.layers)

    @property
    def S_conv_to_surface_col(self) -> ArrayI:
        """Return the conventional-coordinate surface-basis certificate."""
        return self.transforms.S_conv_to_surface_col

    @property
    def P_supercell_row(self) -> ArrayI:
        """Integer supercell matrix for ASE ``make_supercell`` (row convention)."""
        return self.transforms.P_supercell_row

    @property
    def R_conv_to_slab(self) -> ArrayF:
        """Rotation mapping Cartesian vectors: x_slab = R x_conv."""
        return self.transforms.R_conv_to_slab

    @property
    def R_slab_to_conv(self) -> ArrayF:
        """Inverse rotation mapping Cartesian vectors: x_conv = R^T x_slab."""
        return self.transforms.R_slab_to_conv


def _construct_slab_frame_rotation(
    surface_normal: ArrayF,
    inplane_vector: ArrayF,
    normal_sign: int = +1,
    *,
    ortho_tol: float = 1e-10,
) -> ArrayF:
    """Return the proper map ``x_slab = R @ x_conventional``."""
    return _compute_R_from_normal_and_inplane(
        surface_normal,
        inplane_vector,
        normal_sign=normal_sign,
        ortho_tol=ortho_tol,
    )


def build_oriented_slab(
    bulk: "Bulk",
    *,
    hkl: tuple[int, int, int],
    layers: int,
    symprec: float = 1e-5,
    reduce_inplane: bool = True,
    primitive_max_denominator: int = DEFAULT_PRIMITIVE_MAX_DENOMINATOR,
    primitive_reduction_max_iter: int = DEFAULT_PRIMITIVE_REDUCTION_MAX_ITER,
    stacking_search_radius: int = DEFAULT_STACKING_SEARCH_RADIUS,
    normal_sign: int = +1,
    z_tolerance: float = 1e-10,
    ortho_tol: float = 1e-10,
    reduce_c_tilt: bool = True,
    c_tilt_search: int = DEFAULT_C_TILT_SEARCH_RADIUS,
    c_tilt_singular_tolerance: float = DEFAULT_C_TILT_SINGULAR_TOLERANCE,
    orthogonalize_c: bool = False,
    vacuum: float | None = None,
    center_slab: bool = True,
    unwrap_before_vacuum: bool = True,
    wrap: bool = True,
) -> OrientedSlabResult:
    """Build an oriented primitive-bulk surface block and optional slab.

    Miller indices are defined in the conventional bulk basis.  The exact
    primitive surface-plane stage maps that covector into primitive coordinates
    and constructs a saturated integer kernel plus a one-step stacking vector.
    ``layers`` repeats that primitive stacking step exactly.

    The construction then composes, in order:

    1. an integer primitive-bulk supercell;
    2. a proper Cartesian rotation into the slab frame;
    3. an optional unimodular in-plane metric gauge and proper alignment;
    4. an optional bounded integer c-tilt gauge;
    5. an optional physical c-orthogonalization shear;
    6. an orientation-preserving canonical sign gauge; and
    7. optional Cartesian-z vacuum padding with an orthogonal boundary vector.

    The primitive bulk-induced Bravais surface lattice is exact.  Decorated
    finite-slab motif minimality is a separate physical question and is not
    inferred through a tolerance-dependent translation search.
    """

    if make_supercell is None:  # pragma: no cover
        from calm.exceptions import optional_dependency_error

        raise optional_dependency_error(
            missing="ase",
            extra="science",
            symbol="oriented slab construction",
        )

    layer_count = _positive_integer("layers", layers)
    sign = _normal_sign(normal_sign)
    metric_tolerance = _nonnegative_finite_float("symprec", symprec)
    alignment_tolerance = _nonnegative_finite_float(
        "z_tolerance",
        z_tolerance,
    )
    rotation_tolerance = _nonnegative_finite_float("ortho_tol", ortho_tol)
    denominator_bound = _positive_integer(
        "primitive_max_denominator",
        primitive_max_denominator,
    )
    reduction_iteration_limit = _positive_integer(
        "primitive_reduction_max_iter",
        primitive_reduction_max_iter,
    )
    stacking_radius = _positive_integer(
        "stacking_search_radius",
        stacking_search_radius,
    )
    search_radius = _positive_integer("c_tilt_search", c_tilt_search)
    c_tilt_singular = _positive_finite_float(
        "c_tilt_singular_tolerance",
        c_tilt_singular_tolerance,
    )
    padding = None
    if vacuum is not None:
        padding = _nonnegative_finite_float("vacuum", vacuum)

    conventional = bulk.conv.copy()
    primitive = bulk.prim.copy()
    if not np.all(conventional.get_pbc()) or not np.all(primitive.get_pbc()):
        raise ValueError("Expected fully periodic conventional and primitive cells")
    if len(primitive) == 0:
        raise ValueError("Primitive bulk cell must contain at least one atom")

    hkl_reduced = _reduce_hkl(hkl)

    # Conventional-coordinate certificate retained for crystallographic
    # provenance.  The actual atomistic supercell below is constructed from the
    # primitive cell using the mapped primitive Miller covector.
    surface_basis_conventional = surface_basis_S_from_hkl(hkl_reduced)
    surface_basis_layers = surface_basis_conventional.copy().astype(int)
    surface_basis_layers[:, 2] *= layer_count

    conventional_columns = conventional.cell.array.T
    primitive_columns = primitive.cell.array.T
    u, v, w, miller_primitive_array = compute_primitive_surface_basis(
        hkl_reduced[0],
        hkl_reduced[1],
        hkl_reduced[2],
        conventional_columns,
        primitive_columns,
        max_denominator=denominator_bound,
        reduction_max_iter=reduction_iteration_limit,
        stacking_search_radius=stacking_radius,
    )
    primitive_supercell_col = np.column_stack([u, v, layer_count * w]).astype(int)
    signed_index = int(np.dot(np.cross(u, v), layer_count * w))
    if signed_index != layer_count:
        raise RuntimeError(
            "Primitive surface supercell must be right-handed with signed "
            f"index {layer_count}; got {signed_index}."
        )
    primitive_supercell_row = supercell_matrix_ase_from_col(primitive_supercell_col)
    initial = make_supercell_col(primitive, primitive_supercell_col)

    oriented, rotation_ungauged = _orient_block_to_slab_frame(
        initial,
        normal_sign=sign,
        ortho_tol=rotation_tolerance,
    )
    positions = np.asarray(oriented.get_positions(), dtype=float)
    positions[:, 2] -= float(np.min(positions[:, 2]))
    oriented.set_positions(positions)

    inplane_transform = None
    alignment_rotation = None
    if reduce_inplane:
        oriented, inplane_transform, alignment_rotation = _reduce_inplane_by_metric(
            oriented,
            symprec=metric_tolerance,
        )
    rotation_total = (
        np.asarray(alignment_rotation, dtype=float) @ rotation_ungauged
        if alignment_rotation is not None
        else rotation_ungauged
    )

    c_tilt_transform = None
    c_tilt_pair = None
    if reduce_c_tilt:
        oriented, c_tilt_pair, c_tilt_transform = _reduce_c_tilt_integer(
            oriented,
            search=search_radius,
            singular_tol=c_tilt_singular,
        )

    shear_info = None
    block = oriented
    if orthogonalize_c:
        block, shear_info = _orthogonalize_c_by_shear(
            block,
            z_axis=2,
            z_tol=alignment_tolerance,
        )

    canonical_fix = _apply_canonical_sign_fix(block)
    assess_oriented_surface_cell(
        block.cell.array,
        name="Final periodic slab block cell",
    )

    slab = block
    vacuum_info = None
    if padding is not None and padding > 0.0:
        slab, vacuum_info = _add_vacuum_along_cartesian_z(
            block,
            padding,
            center=center_slab,
            unwrap_first=unwrap_before_vacuum,
            z_axis=2,
            z_tol=alignment_tolerance,
        )

    block, slab = _finalize_wrap_and_clamp(block, slab, wrap=wrap)
    transforms = _construct_transforms(
        hkl_red=hkl_reduced,
        layers=layer_count,
        S_layers=surface_basis_layers,
        U_inplane=inplane_transform,
        P_row_used=primitive_supercell_row,
        R_conv_to_slab_total=rotation_total,
        R_align=alignment_rotation,
        L_c_tilt_row=c_tilt_transform,
        mn=c_tilt_pair,
        shear_info=shear_info,
        vacuum_info=vacuum_info,
        canonical_fix=canonical_fix,
        construction_controls=bounded_surface_gauge_controls(
            construction_path="primitive_bulk",
            primitive_max_denominator=denominator_bound,
            primitive_reduction_max_iter=reduction_iteration_limit,
            stacking_search_radius=stacking_radius,
            reduce_c_tilt=reduce_c_tilt,
            c_tilt_search=search_radius,
            c_tilt_singular_tolerance=c_tilt_singular,
        ),
        supercell_reference="primitive",
        miller_primitive=tuple(int(value) for value in miller_primitive_array.tolist()),
    )
    return OrientedSlabResult(block=block, slab=slab, transforms=transforms)
