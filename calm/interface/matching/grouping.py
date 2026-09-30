"""Versioned numerical post-processing groups for interface prototypes.

The relations in this module are deliberately weaker than scientific identity.
Metric and contact-motif keys are self-describing numerical bins with explicit
units, quantization, quotient actions, versions, and collision limitations.
They are useful for analysis but never prove crystallographic or atomistic
equivalence.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from calm.math2d.normal_forms import hnf2_col

MetricSig2D = tuple[int, int, int]

NUMERICAL_GROUPING_POLICY = "numerical_metric_then_contact_motif"
NUMERICAL_GROUPING_POLICY_VERSION = 1
METRIC_GROUPING_KEY_VERSION = 1
CONTACT_MOTIF_GROUPING_KEY_VERSION = 1


@dataclass(frozen=True, order=True)
class MetricGroupingKey2D:
    """Versioned numerical bin for one reduced two-dimensional Gram tensor.

    Equality of these keys means only that all three independent Gram entries
    landed in the same declared half-to-even quantization bins.  It is not
    exact lattice identity and it is not a pairwise distance-within-tolerance
    relation.
    """

    quantized_gram: MetricSig2D
    quantization_step_angstrom2: float
    signature_version: int = METRIC_GROUPING_KEY_VERSION
    relation: str = "tolerance_defined_numerical_grouping"
    gram_unit: str = "angstrom^2"
    rounding: str = "nearest_half_to_even"
    normalization: str = "none_absolute_binning"
    input_representation: str = "canonical_reduced_spd_gram"
    cartesian_orthogonal_quotient: str = "via_gram"
    symmetry_validation: str = "max_asymmetry_le_64eps_times_max_one_or_max_abs_entry"
    collision_possible: bool = True

    def to_dict(self) -> dict[str, object]:
        """Return JSON-native grouping provenance."""
        return {
            "signature_version": self.signature_version,
            "relation": self.relation,
            "gram_unit": self.gram_unit,
            "quantization_step_angstrom2": self.quantization_step_angstrom2,
            "rounding": self.rounding,
            "normalization": self.normalization,
            "input_representation": self.input_representation,
            "cartesian_orthogonal_quotient": (self.cartesian_orthogonal_quotient),
            "symmetry_validation": self.symmetry_validation,
            "quantized_gram": list(self.quantized_gram),
            "collision_possible": self.collision_possible,
        }


@dataclass(frozen=True, order=True)
class ContactMotifGroupingKey2D:
    """Versioned numerical grouping key for one selected contact motif.

    The digest is species resolved and quotients atom order plus primitive-cell
    translations within the declared supercell.  It does not quotient surface
    point-group operations, and coordinate quantization can merge distinct
    motifs.
    """

    digest: str
    side: str
    z_window_angstrom: float
    fractional_quantization_step: float
    height_quantization_step_angstrom: float
    signature_version: int = CONTACT_MOTIF_GROUPING_KEY_VERSION
    relation: str = "tolerance_defined_numerical_grouping"
    periodic_translation_quotient: str = (
        "primitive_translations_within_declared_supercell"
    )
    surface_symmetry_quotient: str = "none"
    species_policy: str = "atomic_number_exact"
    layer_selection_boundary: str = "inclusive"
    rounding: str = "nearest_half_to_even"
    normalization: str = "fractional_xy_and_relative_height"
    digest_algorithm: str = "sha256_little_endian_int64_v1"
    collision_possible: bool = True

    def to_dict(self) -> dict[str, object]:
        """Return JSON-native grouping provenance."""
        return {
            "signature_version": self.signature_version,
            "relation": self.relation,
            "side": self.side,
            "z_window_angstrom": self.z_window_angstrom,
            "fractional_quantization_step": self.fractional_quantization_step,
            "height_quantization_step_angstrom": (
                self.height_quantization_step_angstrom
            ),
            "periodic_translation_quotient": (self.periodic_translation_quotient),
            "surface_symmetry_quotient": self.surface_symmetry_quotient,
            "species_policy": self.species_policy,
            "layer_selection_boundary": self.layer_selection_boundary,
            "rounding": self.rounding,
            "normalization": self.normalization,
            "digest_algorithm": self.digest_algorithm,
            "digest": self.digest,
            "collision_possible": self.collision_possible,
        }


MetricGroupingPair = tuple[MetricGroupingKey2D, MetricGroupingKey2D]
ContactMotifGroupingPair = tuple[ContactMotifGroupingKey2D, ContactMotifGroupingKey2D]


def _finite_positive_float(name: str, value: object) -> float:
    """Return a finite positive floating-point value."""
    if isinstance(value, (bool, np.bool_)):
        raise TypeError(f"{name} must be a real number, not a Boolean.")
    result = float(value)
    if not np.isfinite(result) or result <= 0.0:
        raise ValueError(f"{name} must be finite and positive.")
    return result


def _finite_nonnegative_float(name: str, value: object) -> float:
    """Return a finite nonnegative floating-point value."""
    if isinstance(value, (bool, np.bool_)):
        raise TypeError(f"{name} must be a real number, not a Boolean.")
    result = float(value)
    if not np.isfinite(result) or result < 0.0:
        raise ValueError(f"{name} must be finite and nonnegative.")
    return result


def _decimal_count(name: str, value: object) -> int:
    """Return a practical exact decimal count for float quantization."""
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
        raise TypeError(f"{name} must be an integer.")
    count = int(value)
    if count < 0 or count > 15:
        raise ValueError(f"{name} must lie between 0 and 15.")
    return count


def _integer_matrix_2x2(name: str, value: object) -> np.ndarray:
    """Return a strict full-rank 2x2 integer matrix."""
    matrix = np.asarray(value)
    if matrix.shape != (2, 2):
        raise ValueError(f"{name} must have shape (2, 2).")
    if matrix.dtype.kind not in {"i", "u"}:
        raise TypeError(f"{name} must contain exact integer values.")
    matrix_int = np.asarray(matrix, dtype=int)
    determinant = int(
        matrix_int[0, 0] * matrix_int[1, 1] - matrix_int[0, 1] * matrix_int[1, 0]
    )
    if determinant == 0:
        raise ValueError(f"{name} must have nonzero determinant.")
    return matrix_int


def _quantize_metric_gram_2d(
    G: np.ndarray,
    *,
    scale: float = 1e10,
) -> MetricSig2D:
    """Return the quantized independent entries of a 2D Gram tensor."""
    metric_scale = _finite_positive_float("scale", scale)
    matrix = np.asarray(G, dtype=float)
    if matrix.shape != (2, 2):
        raise ValueError("G must have shape (2, 2).")
    if not np.all(np.isfinite(matrix)):
        raise ValueError("G must contain only finite values.")
    symmetric = 0.5 * matrix + 0.5 * matrix.T
    eigenvalues = np.linalg.eigvalsh(symmetric)
    if np.any(eigenvalues <= 0.0):
        raise ValueError("G must be positive definite.")
    independent = np.asarray(
        [symmetric[0, 0], symmetric[0, 1], symmetric[1, 1]],
        dtype=float,
    )
    with np.errstate(over="ignore", invalid="ignore"):
        scaled = metric_scale * independent
    if not np.all(np.isfinite(scaled)):
        raise ValueError("scale * G must remain finite for metric quantization.")
    return tuple(int(np.rint(value)) for value in scaled)


def metric_grouping_key_2d(
    G: np.ndarray,
    *,
    quantization_step_angstrom2: float = 1e-10,
) -> MetricGroupingKey2D:
    """Return a self-describing numerical grouping key for a reduced metric.

    ``G`` is interpreted in square angstroms.  Each independent entry is
    divided by ``quantization_step_angstrom2`` and rounded to the nearest
    integer using NumPy's half-to-even rule.  Equality therefore means same
    quantization bin, not exact crystallographic identity.
    """
    step = _finite_positive_float(
        "quantization_step_angstrom2", quantization_step_angstrom2
    )
    matrix = np.asarray(G, dtype=float)
    if matrix.shape != (2, 2):
        raise ValueError("G must have shape (2, 2).")
    if not np.all(np.isfinite(matrix)):
        raise ValueError("G must contain only finite values.")
    matrix_scale = max(1.0, float(np.max(np.abs(matrix))))
    symmetry_tolerance = 64.0 * np.finfo(float).eps * matrix_scale
    if float(np.max(np.abs(matrix - matrix.T))) > symmetry_tolerance:
        raise ValueError(
            "G must be symmetric within 64 machine eps times its entry scale."
        )
    scale = 1.0 / step
    if not np.isfinite(scale) or scale <= 0.0:
        raise ValueError(
            "quantization_step_angstrom2 is too small for finite quantization."
        )
    return MetricGroupingKey2D(
        quantized_gram=_quantize_metric_gram_2d(matrix, scale=scale),
        quantization_step_angstrom2=step,
    )


def _atoms_from_slab(slab: Any) -> Any:
    """Return an ASE-like atoms object from a slab or atoms-like input."""
    atoms = getattr(slab, "atoms", slab)
    if not hasattr(atoms, "positions") or not hasattr(atoms, "cell"):
        raise TypeError(
            "slab must expose an atoms-like object with positions and cell."
        )
    return atoms


def _primitive_inplane_basis_2d(slab: Any) -> np.ndarray:
    """Return the slab's in-plane column basis with scale-free validation."""
    atoms = _atoms_from_slab(slab)
    cell = np.asarray(atoms.cell.array, dtype=float)
    if cell.shape != (3, 3) or not np.all(np.isfinite(cell)):
        raise ValueError("The slab cell must be a finite 3x3 matrix.")
    inplane_rows = cell[:2, :]
    scale = float(np.max(np.abs(inplane_rows)))
    if not np.isfinite(scale) or scale <= 0.0:
        raise ValueError("The slab in-plane basis must have nonzero finite scale.")
    frame_tolerance = 64.0 * np.finfo(float).eps * scale
    if np.max(np.abs(inplane_rows[:, 2])) > frame_tolerance:
        raise ValueError(
            "The slab in-plane vectors must lie in the global Cartesian xy plane."
        )
    basis = inplane_rows[:, :2].T
    normalized = basis / scale
    if abs(float(np.linalg.det(normalized))) <= 64.0 * np.finfo(float).eps:
        raise ValueError("The slab in-plane basis is numerically rank deficient.")
    return basis


def _contact_atom_mask(
    slab: Any,
    *,
    side: str,
    z_tol: float,
) -> np.ndarray:
    """Select the requested top, bottom, or complete slab contact layer."""
    atoms = _atoms_from_slab(slab)
    positions = np.asarray(atoms.positions, dtype=float)
    if positions.ndim != 2 or positions.shape[1] != 3 or positions.shape[0] == 0:
        raise ValueError("The slab must contain at least one finite 3D position.")
    if not np.all(np.isfinite(positions)):
        raise ValueError("The slab positions must be finite.")
    tolerance = _finite_nonnegative_float("z_tol", z_tol)
    z = positions[:, 2]

    if side == "all":
        return np.ones(z.shape[0], dtype=bool)
    if side == "top":
        return (float(np.max(z)) - z) <= tolerance
    if side == "bottom":
        return (z - float(np.min(z))) <= tolerance
    raise ValueError("side must be 'top', 'bottom', or 'all'.")


def _coset_representatives_from_hnf(hnf: np.ndarray) -> np.ndarray:
    """Enumerate one representative of every class in ``Z^2/HZ^2``."""
    canonical = hnf2_col(_integer_matrix_2x2("hnf", hnf))
    h11 = int(canonical[0, 0])
    h22 = int(canonical[1, 1])
    return np.asarray(
        [(x, y) for y in range(h22) for x in range(h11)],
        dtype=int,
    )


def _atomic_numbers(atoms: Any, count: int) -> np.ndarray:
    """Return one integer atomic number per position."""
    if hasattr(atoms, "numbers"):
        numbers = np.asarray(atoms.numbers)
    elif hasattr(atoms, "get_atomic_numbers"):
        numbers = np.asarray(atoms.get_atomic_numbers())
    else:
        raise TypeError("The atoms-like object must expose atomic numbers.")
    if numbers.shape != (count,) or numbers.dtype.kind not in {"i", "u"}:
        raise ValueError("Atomic numbers must be an integer vector matching positions.")
    return np.asarray(numbers, dtype=np.int64)


def _packed_records_key(records: np.ndarray) -> tuple[tuple[int, ...], ...]:
    """Return a numeric lexicographic key for canonicalization."""
    return tuple(tuple(int(value) for value in row) for row in records)


def _supercell_contact_motif_signature_2d(
    slab: Any,
    N_tot: np.ndarray,
    *,
    side: str,
    z_tol: float = 0.25,
    xy_decimals: int = 8,
    z_decimals: int = 3,
) -> str:
    """Return a deterministic contact-layer signature in one 2D supercell.

    The signature is invariant to atom order and to primitive-cell translations
    inside the declared supercell.  It is species resolved and includes the
    selected layer's relative height profile.  It remains a quantized grouping
    heuristic, not a complete structural invariant.
    """
    supercell = _integer_matrix_2x2("N_tot", N_tot)
    xy_digits = _decimal_count("xy_decimals", xy_decimals)
    z_digits = _decimal_count("z_decimals", z_decimals)
    tolerance = _finite_nonnegative_float("z_tol", z_tol)

    atoms = _atoms_from_slab(slab)
    positions = np.asarray(atoms.positions, dtype=float)
    mask = _contact_atom_mask(slab, side=side, z_tol=tolerance)
    selected = positions[mask]
    numbers = _atomic_numbers(atoms, positions.shape[0])[mask]
    basis = _primitive_inplane_basis_2d(slab)

    primitive_fractional = selected[:, :2] @ np.linalg.inv(basis).T
    primitive_fractional %= 1.0

    if side == "top":
        relative_z = float(np.max(positions[:, 2])) - selected[:, 2]
    elif side == "bottom":
        relative_z = selected[:, 2] - float(np.min(positions[:, 2]))
    else:
        relative_z = selected[:, 2] - float(np.min(selected[:, 2]))

    canonical_supercell = hnf2_col(supercell)
    representatives = _coset_representatives_from_hnf(canonical_supercell)
    inverse_supercell = np.linalg.inv(canonical_supercell.astype(float))

    fractional_blocks: list[np.ndarray] = []
    number_blocks: list[np.ndarray] = []
    height_blocks: list[np.ndarray] = []
    for translation in representatives:
        block = (
            primitive_fractional + translation[np.newaxis, :]
        ) @ inverse_supercell.T
        block %= 1.0
        fractional_blocks.append(block)
        number_blocks.append(numbers)
        height_blocks.append(relative_z)

    fractional = np.vstack(fractional_blocks)
    tiled_numbers = np.concatenate(number_blocks)
    tiled_heights = np.concatenate(height_blocks)
    xy_scale = 10**xy_digits
    z_scale = 10**z_digits
    qx = np.rint(fractional[:, 0] * xy_scale).astype(np.int64) % xy_scale
    qy = np.rint(fractional[:, 1] * xy_scale).astype(np.int64) % xy_scale
    qz = np.rint(tiled_heights * z_scale).astype(np.int64)

    shifts = representatives @ inverse_supercell.T
    sx_values = np.rint(shifts[:, 0] * xy_scale).astype(np.int64) % xy_scale
    sy_values = np.rint(shifts[:, 1] * xy_scale).astype(np.int64) % xy_scale

    best_key: tuple[tuple[int, ...], ...] | None = None
    best_records: np.ndarray | None = None
    for sx, sy in zip(sx_values, sy_values, strict=True):
        shifted_x = (qx - sx) % xy_scale
        shifted_y = (qy - sy) % xy_scale
        order = np.lexsort((shifted_y, shifted_x, qz, tiled_numbers))
        records = np.column_stack(
            [tiled_numbers[order], qz[order], shifted_x[order], shifted_y[order]]
        ).astype(np.int64, copy=False)
        key = _packed_records_key(records)
        if best_key is None or key < best_key:
            best_key = key
            best_records = records

    if best_records is None:  # pragma: no cover - nonempty finite quotient
        raise RuntimeError("Failed to canonicalize the contact-layer motif.")
    portable = np.ascontiguousarray(best_records, dtype=np.dtype("<i8"))
    return hashlib.sha256(portable.tobytes()).hexdigest()


def contact_motif_grouping_key_2d(
    slab: Any,
    N_tot: np.ndarray,
    *,
    side: str,
    z_window_angstrom: float = 0.25,
    xy_decimals: int = 8,
    z_decimals: int = 3,
) -> ContactMotifGroupingKey2D:
    """Return a self-describing numerical contact-motif grouping key.

    The z-window is an inclusive Cartesian distance in angstroms.  In-plane
    coordinates are fractional and quantized at ``10**(-xy_decimals)``; relative
    heights are in angstroms and quantized at ``10**(-z_decimals)``.  Atom order
    and primitive-cell translations within the declared supercell are quotiented.
    Surface point-group operations are deliberately not quotiented.
    """
    window = _finite_nonnegative_float("z_window_angstrom", z_window_angstrom)
    xy_digits = _decimal_count("xy_decimals", xy_decimals)
    z_digits = _decimal_count("z_decimals", z_decimals)
    digest = _supercell_contact_motif_signature_2d(
        slab,
        N_tot,
        side=side,
        z_tol=window,
        xy_decimals=xy_digits,
        z_decimals=z_digits,
    )
    return ContactMotifGroupingKey2D(
        digest=digest,
        side=side,
        z_window_angstrom=window,
        fractional_quantization_step=10.0 ** (-xy_digits),
        height_quantization_step_angstrom=10.0 ** (-z_digits),
    )


@dataclass(frozen=True)
class NumericalMetricGroup:
    """One versioned numerical metric bin split into contact-motif bins."""

    metric_grouping_key_A: MetricGroupingKey2D
    metric_grouping_key_B: MetricGroupingKey2D
    variants: dict[ContactMotifGroupingPair, list[Any]]
    grouping_policy: str = NUMERICAL_GROUPING_POLICY
    grouping_policy_version: int = NUMERICAL_GROUPING_POLICY_VERSION
    relation: str = "tolerance_defined_numerical_grouping"
    exact_identity: bool = False
    collision_limitations: tuple[str, ...] = (
        "different Gram tensors can occupy one quantization bin",
        "different contact motifs can occupy one coordinate-quantization bin",
        "surface point-group operations are not quotiented",
    )


def _record_rank(record: Any) -> tuple[object, ...]:
    """Return a deterministic order for candidates or public prototypes."""
    return (
        float(getattr(record, "match_score", float("inf"))),
        float(
            getattr(
                record,
                "d_cell",
                getattr(getattr(record, "ai_strain", None), "d_cell", float("inf")),
            )
        ),
        str(getattr(record, "prototype_uid", "")),
        tuple(
            int(value)
            for value in np.asarray(
                getattr(getattr(record, "supercell_a", None), "N_tot", ())
            ).ravel()
        ),
        tuple(
            int(value)
            for value in np.asarray(
                getattr(getattr(record, "supercell_b", None), "N_tot", ())
            ).ravel()
        ),
    )


def _group_records(
    records: Sequence[Any],
    *,
    slab_a_for: Any,
    slab_b_for: Any,
    supercell_a_for: Any,
    supercell_b_for: Any,
    contact_side_A: str,
    contact_side_B: str,
    z_window_angstrom: float,
    metric_quantization_step_angstrom2: float,
    xy_decimals: int,
    z_decimals: int,
) -> dict[MetricGroupingPair, NumericalMetricGroup]:
    """Group records through caller-supplied slab and supercell accessors."""
    raw: dict[
        MetricGroupingPair,
        dict[ContactMotifGroupingPair, list[Any]],
    ] = {}
    metric_cache: dict[tuple[int, tuple[int, ...]], MetricGroupingKey2D] = {}
    motif_cache: dict[tuple[object, ...], ContactMotifGroupingKey2D] = {}

    for record in records:
        cell_a = supercell_a_for(record)
        cell_b = supercell_b_for(record)
        matrix_a = _integer_matrix_2x2("N_tot_A", cell_a.N_tot)
        matrix_b = _integer_matrix_2x2("N_tot_B", cell_b.N_tot)
        matrix_key_a = tuple(int(value) for value in matrix_a.ravel())
        matrix_key_b = tuple(int(value) for value in matrix_b.ravel())

        metric_cache_key_a = (id(cell_a), matrix_key_a)
        metric_a = metric_cache.get(metric_cache_key_a)
        if metric_a is None:
            metric_a = metric_grouping_key_2d(
                cell_a.G_red,
                quantization_step_angstrom2=(metric_quantization_step_angstrom2),
            )
            metric_cache[metric_cache_key_a] = metric_a
        metric_cache_key_b = (id(cell_b), matrix_key_b)
        metric_b = metric_cache.get(metric_cache_key_b)
        if metric_b is None:
            metric_b = metric_grouping_key_2d(
                cell_b.G_red,
                quantization_step_angstrom2=(metric_quantization_step_angstrom2),
            )
            metric_cache[metric_cache_key_b] = metric_b

        slab_a = slab_a_for(record)
        slab_b = slab_b_for(record)
        motif_key_a = (
            id(slab_a),
            matrix_key_a,
            contact_side_A,
            float(z_window_angstrom),
            int(xy_decimals),
            int(z_decimals),
        )
        motif_a = motif_cache.get(motif_key_a)
        if motif_a is None:
            motif_a = contact_motif_grouping_key_2d(
                slab_a,
                matrix_a,
                side=contact_side_A,
                z_window_angstrom=z_window_angstrom,
                xy_decimals=xy_decimals,
                z_decimals=z_decimals,
            )
            motif_cache[motif_key_a] = motif_a

        motif_key_b = (
            id(slab_b),
            matrix_key_b,
            contact_side_B,
            float(z_window_angstrom),
            int(xy_decimals),
            int(z_decimals),
        )
        motif_b = motif_cache.get(motif_key_b)
        if motif_b is None:
            motif_b = contact_motif_grouping_key_2d(
                slab_b,
                matrix_b,
                side=contact_side_B,
                z_window_angstrom=z_window_angstrom,
                xy_decimals=xy_decimals,
                z_decimals=z_decimals,
            )
            motif_cache[motif_key_b] = motif_b

        raw.setdefault((metric_a, metric_b), {}).setdefault(
            (motif_a, motif_b), []
        ).append(record)

    grouped: dict[MetricGroupingPair, NumericalMetricGroup] = {}
    for metric_pair in sorted(raw):
        variants = raw[metric_pair]
        ordered_variants = {
            motif_pair: sorted(variants[motif_pair], key=_record_rank)
            for motif_pair in sorted(variants)
        }
        grouped[metric_pair] = NumericalMetricGroup(
            metric_grouping_key_A=metric_pair[0],
            metric_grouping_key_B=metric_pair[1],
            variants=ordered_variants,
        )
    return grouped


def group_prototypes_by_numerical_metric_then_contact_motif(
    prototypes: Sequence[Any],
    *,
    contact_side_A: str = "top",
    contact_side_B: str = "bottom",
    z_window_angstrom: float = 0.25,
    metric_quantization_step_angstrom2: float = 1e-10,
    xy_decimals: int = 8,
    z_decimals: int = 3,
) -> dict[MetricGroupingPair, NumericalMetricGroup]:
    """Group prototypes by explicitly versioned numerical binning policies.

    This is post-processing for exploratory analysis.  It does not alter exact
    candidate identity, crystallographic equivalence, deduplication, or Pareto
    classification.
    """
    return _group_records(
        prototypes,
        slab_a_for=lambda prototype: prototype.slab_a,
        slab_b_for=lambda prototype: prototype.slab_b,
        supercell_a_for=lambda prototype: prototype.supercell_a,
        supercell_b_for=lambda prototype: prototype.supercell_b,
        contact_side_A=contact_side_A,
        contact_side_B=contact_side_B,
        z_window_angstrom=z_window_angstrom,
        metric_quantization_step_angstrom2=(metric_quantization_step_angstrom2),
        xy_decimals=xy_decimals,
        z_decimals=z_decimals,
    )
