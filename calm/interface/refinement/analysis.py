"""Strain decomposition and crystallographic direction analysis.

The module separates three coordinate systems that must not be conflated:

1. the final oriented-slab Cartesian frame in which CALM computes the in-plane
   Hencky strain tensor;
2. the parent bulk conventional Cartesian frame; and
3. coordinates in the conventional lattice basis, conventionally written as
   crystallographic direction coefficients ``[u v w]``.

Principal directions are line directions. Their signs are therefore gauge
choices, and repeated or numerically unresolved principal strains do not define
individual axes at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import reduce
from itertools import product
from math import gcd

import numpy as np


DirectionStatus = str


@dataclass(frozen=True)
class StrainDecomposition:
    """Complete decomposition of a two-dimensional Hencky strain tensor.

    ``principal_directions`` is available only when the eigengap is sufficiently
    resolved. For repeated or near-repeated principal strains, CALM reports the
    full unresolved in-plane eigenspace through
    ``principal_eigenspace_projector`` instead of exposing arbitrary eigenvectors.
    """

    principal_strains: np.ndarray
    principal_directions: np.ndarray | None
    E: np.ndarray
    E_area: np.ndarray
    E_shape: np.ndarray
    norm_E: float
    norm_E_area: float
    norm_E_shape: float
    trace_E: float
    direction_status: DirectionStatus = "defined"
    principal_eigengap: float | None = None
    principal_eigengap_threshold: float | None = None
    principal_eigenspace_projector: np.ndarray | None = None

    def __post_init__(self) -> None:
        """Validate shape and decomposition invariants."""
        self._validate_principal_strains()
        self._validate_direction_state()
        self._validate_tensor_shapes()
        self._initialize_and_validate_eigengap()
        self._validate_norm_decomposition()

    def _validate_principal_strains(self) -> None:
        if self.principal_strains.shape != (2,):
            raise ValueError(
                "principal_strains must have shape (2,), got "
                f"{self.principal_strains.shape}"
            )

    def _validate_direction_state(self) -> None:
        if self.direction_status not in {
            "defined",
            "near_degenerate",
            "degenerate",
        }:
            raise ValueError(
                "direction_status must be defined, near_degenerate, or degenerate"
            )
        if self.principal_directions is not None:
            self._validate_resolved_direction_matrix()
        if self.direction_status == "defined":
            self._validate_defined_directions()
        else:
            self._validate_unresolved_directions()

    def _validate_resolved_direction_matrix(self) -> None:
        directions = self.principal_directions
        assert directions is not None
        if directions.shape != (2, 2):
            raise ValueError(
                f"principal_directions must have shape (2,2), got {directions.shape}"
            )
        orthogonality = directions.T @ directions
        if not np.allclose(orthogonality, np.eye(2), atol=1.0e-12):
            raise ValueError("principal_directions must be orthonormal")

    def _validate_defined_directions(self) -> None:
        if self.principal_directions is None:
            raise ValueError(
                "defined principal directions require explicit eigenvectors"
            )
        if self.principal_eigenspace_projector is not None:
            raise ValueError(
                "defined principal directions do not use a subspace projector"
            )

    def _validate_unresolved_directions(self) -> None:
        if self.principal_directions is not None:
            raise ValueError(
                "unresolved principal directions must not expose eigenvectors"
            )
        projector = self.principal_eigenspace_projector
        if projector is None or projector.shape != (2, 2):
            raise ValueError("unresolved directions require a 2x2 eigenspace projector")
        if not np.allclose(projector, np.eye(2), atol=1.0e-12):
            raise ValueError("a repeated 2D eigenspace must span the complete plane")

    def _validate_tensor_shapes(self) -> None:
        if self.E.shape != (2, 2):
            raise ValueError(f"E must have shape (2,2), got {self.E.shape}")
        if self.E_area.shape != (2, 2) or self.E_shape.shape != (2, 2):
            raise ValueError("E_area and E_shape must have shape (2,2)")

    def _initialize_and_validate_eigengap(self) -> None:
        eigengap = self.principal_eigengap
        if eigengap is None:
            eigengap = float(abs(self.principal_strains[1] - self.principal_strains[0]))
            object.__setattr__(self, "principal_eigengap", eigengap)
        threshold = self.principal_eigengap_threshold
        if threshold is None:
            threshold = 0.0
            object.__setattr__(
                self,
                "principal_eigengap_threshold",
                threshold,
            )
        if eigengap < 0.0:
            raise ValueError("principal_eigengap must be nonnegative")
        if threshold < 0.0:
            raise ValueError("principal_eigengap_threshold must be nonnegative")

    def _validate_norm_decomposition(self) -> None:
        norm_sq_sum = self.norm_E_area**2 + self.norm_E_shape**2
        norm_sq_E = self.norm_E**2
        rel_error = abs(norm_sq_E - norm_sq_sum) / max(norm_sq_E, 1.0e-30)
        if rel_error > 1.0e-6:
            raise ValueError(
                "Strain decomposition failed orthogonality check: "
                f"||E||^2 = {norm_sq_E:.6e}, "
                "||E_area||^2 + ||E_shape||^2 = "
                f"{norm_sq_sum:.6e}"
            )

    @property
    def max_principal_strain(self) -> float:
        """Return the maximum absolute principal strain."""
        return float(np.max(np.abs(self.principal_strains)))

    @property
    def log_area_ratio(self) -> float:
        """Return ``ln(A_2/A_1) = epsilon_1 + epsilon_2``."""
        return self.trace_E

    @property
    def area_ratio(self) -> float:
        """Return ``A_2/A_1 = exp(epsilon_1 + epsilon_2)``."""
        return float(np.exp(self.trace_E))


@dataclass(frozen=True)
class CrystallographicDirectionApproximation:
    """Continuous direction and its optional low-index approximation."""

    continuous_coefficients: np.ndarray
    cartesian_direction: np.ndarray
    integer_indices: tuple[int, int, int] | None
    angular_error_deg: float
    formatted: str | None


@dataclass(frozen=True)
class PrincipalDirectionMapping:
    """Resolved principal directions in slab and conventional coordinates."""

    directions_slab_cart: np.ndarray
    directions_conventional_cart: np.ndarray
    directions_conventional: np.ndarray
    approximations: tuple[
        CrystallographicDirectionApproximation,
        CrystallographicDirectionApproximation,
    ]


def _finite_nonnegative(name: str, value: object) -> float:
    result = float(value)
    if not np.isfinite(result) or result < 0.0:
        raise ValueError(f"{name} must be finite and nonnegative")
    return result


def _matrix3(value: object, *, name: str) -> np.ndarray:
    matrix = np.asarray(value, dtype=float)
    if matrix.shape != (3, 3):
        raise ValueError(f"{name} must have shape (3,3), got {matrix.shape}")
    if not np.all(np.isfinite(matrix)):
        raise ValueError(f"{name} must contain only finite values")
    if abs(float(np.linalg.det(matrix))) <= 1.0e-14:
        raise ValueError(f"{name} must be nonsingular")
    return matrix


def _canonicalize_line(vector: np.ndarray, *, atol: float = 1.0e-14) -> np.ndarray:
    """Choose a deterministic sign for a nonzero line direction."""
    out = np.asarray(vector, dtype=float).copy()
    if out.ndim != 1:
        raise ValueError("line direction must be one-dimensional")
    if not np.all(np.isfinite(out)):
        raise ValueError("line direction must contain only finite values")
    norm = float(np.linalg.norm(out))
    if norm <= atol:
        raise ValueError("line direction must be nonzero")
    for component in out:
        if abs(float(component)) > atol:
            if component < 0.0:
                out *= -1.0
            return out
    raise ValueError("line direction is numerically zero")


def _canonicalize_direction_columns(directions: np.ndarray) -> np.ndarray:
    out = np.asarray(directions, dtype=float).copy()
    if out.shape != (2, 2):
        raise ValueError(f"directions must have shape (2,2), got {out.shape}")
    for index in range(2):
        out[:, index] = _canonicalize_line(out[:, index])
    return out


def _classify_direction_status(
    principal_strains: np.ndarray,
    *,
    eigengap_atol: float,
    eigengap_rtol: float,
) -> tuple[DirectionStatus, float, float]:
    eigengap = float(abs(principal_strains[1] - principal_strains[0]))
    scale = max(
        float(np.max(np.abs(principal_strains))),
        float(np.finfo(float).eps),
    )
    threshold = max(eigengap_atol, eigengap_rtol * scale)
    if eigengap <= eigengap_atol:
        return "degenerate", eigengap, threshold
    if eigengap <= threshold:
        return "near_degenerate", eigengap, threshold
    return "defined", eigengap, threshold


def compute_strain_decomposition(
    E_2x2: np.ndarray,
    *,
    eigengap_atol: float = 1.0e-12,
    eigengap_rtol: float = 1.0e-3,
) -> StrainDecomposition:
    """Compute a complete two-dimensional Hencky strain decomposition.

    The principal-axis status is determined from the absolute eigengap and a
    scale-aware relative threshold. Individual directions are withheld for
    repeated or near-repeated principal strains because their orientation is
    then undefined or numerically unstable.
    """
    atol = _finite_nonnegative("eigengap_atol", eigengap_atol)
    rtol = _finite_nonnegative("eigengap_rtol", eigengap_rtol)

    E = np.asarray(E_2x2, dtype=float)
    if E.shape != (2, 2):
        raise ValueError(f"Expected 2x2 strain tensor, got shape {E.shape}")
    if not np.all(np.isfinite(E)):
        raise ValueError("E_2x2 must contain only finite values")
    E = 0.5 * (E + E.T)

    eigvals, eigvecs = np.linalg.eigh(E)
    order = np.argsort(eigvals)
    principal_strains = eigvals[order]
    direction_status, eigengap, threshold = _classify_direction_status(
        principal_strains,
        eigengap_atol=atol,
        eigengap_rtol=rtol,
    )
    if direction_status == "defined":
        principal_directions = _canonicalize_direction_columns(eigvecs[:, order])
        eigenspace_projector = None
    else:
        principal_directions = None
        eigenspace_projector = np.eye(2, dtype=float)

    trace_E = float(np.trace(E))
    E_area = 0.5 * trace_E * np.eye(2)
    E_shape = E - E_area
    norm_E = float(np.linalg.norm(E, ord="fro"))
    norm_E_area = float((np.sqrt(2.0) / 2.0) * abs(trace_E))
    eps1, eps2 = principal_strains
    norm_E_shape = float((np.sqrt(2.0) / 2.0) * abs(eps1 - eps2))

    return StrainDecomposition(
        principal_strains=principal_strains,
        principal_directions=principal_directions,
        direction_status=direction_status,
        principal_eigengap=eigengap,
        principal_eigengap_threshold=threshold,
        principal_eigenspace_projector=eigenspace_projector,
        E=E,
        E_area=E_area,
        E_shape=E_shape,
        norm_E=norm_E,
        norm_E_area=norm_E_area,
        norm_E_shape=norm_E_shape,
        trace_E=trace_E,
    )


def slab_to_conventional_cartesian_map_from_payload(
    payload: object,
) -> np.ndarray:
    """Recover the exact current slab-to-conventional Cartesian map.

    In-memory kernel transform objects may provide the map directly. Persisted
    payloads must use the current compact oriented-slab schema and must contain
    both explicit forward and inverse Cartesian maps. Historical ``U``/rotation
    inference and optional-shear reconstruction are unsupported.
    """

    direct_method = getattr(payload, "M_slab_to_conv_cart", None)
    if callable(direct_method):
        return _matrix3(direct_method(), name="M_slab_to_conv_cart")

    from calm.slab.oriented.transforms import from_transforms_payload

    current = from_transforms_payload(payload).payload
    if "M_slab_to_conv_cart" not in current:
        raise ValueError(
            "Current oriented-slab provenance requires 'M_slab_to_conv_cart'."
        )
    if "M_conv_to_slab_cart" not in current:
        raise ValueError(
            "Current oriented-slab provenance requires 'M_conv_to_slab_cart'."
        )

    inverse_map = _matrix3(
        current["M_slab_to_conv_cart"],
        name="M_slab_to_conv_cart",
    )
    forward_map = _matrix3(
        current["M_conv_to_slab_cart"],
        name="M_conv_to_slab_cart",
    )
    if not np.allclose(
        inverse_map @ forward_map,
        np.eye(3),
        rtol=1.0e-10,
        atol=1.0e-12,
    ):
        raise ValueError("stored slab/conventional Cartesian maps are not inverses")
    return inverse_map


def _mapped_direction_arrays(
    principal_directions_slab_cart: np.ndarray,
    conventional_cell_basis: np.ndarray,
    slab_to_conventional_cart: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    directions_2d = np.asarray(principal_directions_slab_cart, dtype=float)
    if directions_2d.shape != (2, 2):
        raise ValueError(
            "principal_directions_slab_cart must have shape (2,2), got "
            f"{directions_2d.shape}"
        )
    if not np.all(np.isfinite(directions_2d)):
        raise ValueError("principal directions must contain only finite values")
    basis = _matrix3(conventional_cell_basis, name="conventional_cell_basis")
    mapping = _matrix3(
        slab_to_conventional_cart,
        name="slab_to_conventional_cart",
    )

    directions_slab_3d = np.zeros((3, 2), dtype=float)
    directions_slab_3d[:2, :] = directions_2d
    directions_conventional_cart = mapping @ directions_slab_3d
    directions_conventional = np.linalg.solve(
        basis,
        directions_conventional_cart,
    )

    for index in range(2):
        canonical = _canonicalize_line(directions_conventional[:, index])
        dot = float(canonical @ directions_conventional[:, index])
        sign = 1.0 if dot >= 0.0 else -1.0
        directions_slab_3d[:, index] *= sign
        directions_conventional_cart[:, index] *= sign
        directions_conventional[:, index] = canonical
    return (
        directions_slab_3d[:2, :],
        directions_conventional_cart,
        directions_conventional,
    )


def _primitive_integer_direction(values: tuple[int, int, int]) -> tuple[int, int, int]:
    nonzero = [abs(value) for value in values if value != 0]
    divisor = reduce(gcd, nonzero) if nonzero else 1
    reduced = tuple(int(value // divisor) for value in values)
    for value in reduced:
        if value != 0:
            if value < 0:
                return tuple(-item for item in reduced)
            return reduced
    raise ValueError("integer direction must be nonzero")


def _format_integer_direction(indices: tuple[int, int, int]) -> str:
    return f"[{indices[0]} {indices[1]} {indices[2]}]"


def _validated_max_index(max_index: int) -> int:
    if isinstance(max_index, bool) or int(max_index) != max_index:
        raise ValueError("max_index must be a positive integer")
    value = int(max_index)
    if value <= 0 or value > 24:
        raise ValueError("max_index must be an integer in [1, 24]")
    return value


def _unit_cartesian_direction(
    cartesian_direction: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    cartesian = np.asarray(cartesian_direction, dtype=float).copy()
    if cartesian.shape != (3,) or not np.all(np.isfinite(cartesian)):
        raise ValueError("cartesian_direction must be a finite three-vector")
    norm = float(np.linalg.norm(cartesian))
    if norm <= 1.0e-14:
        raise ValueError("cartesian_direction must be nonzero")
    return cartesian, cartesian / norm


def _candidate_integer_directions(
    max_index: int,
) -> set[tuple[int, int, int]]:
    candidates: set[tuple[int, int, int]] = set()
    for values in product(range(-max_index, max_index + 1), repeat=3):
        if values != (0, 0, 0):
            candidates.add(_primitive_integer_direction(values))
    return candidates


def _direction_angular_error_deg(
    reference_unit: np.ndarray,
    candidate_cart: np.ndarray,
) -> float | None:
    norm = float(np.linalg.norm(candidate_cart))
    if norm <= 1.0e-14:
        return None
    candidate_unit = candidate_cart / norm
    sine = float(np.linalg.norm(np.cross(reference_unit, candidate_unit)))
    cosine = float(abs(np.dot(reference_unit, candidate_unit)))
    return float(np.degrees(np.arctan2(sine, cosine)))


def _best_low_index_direction(
    basis: np.ndarray,
    cartesian_unit: np.ndarray,
    *,
    max_index: int,
) -> tuple[tuple[int, int, int], float]:
    best: (
        tuple[
            tuple[float, int, int, tuple[int, int, int]],
            tuple[int, int, int],
        ]
        | None
    ) = None
    for indices in _candidate_integer_directions(max_index):
        candidate_cart = basis @ np.asarray(indices, dtype=float)
        error = _direction_angular_error_deg(cartesian_unit, candidate_cart)
        if error is None:
            continue
        key = (
            error,
            max(abs(value) for value in indices),
            sum(abs(value) for value in indices),
            indices,
        )
        if best is None or key < best[0]:
            best = (key, indices)
    if best is None:
        raise RuntimeError("no low-index crystallographic direction was generated")
    return best[1], best[0][0]


def _approximate_crystallographic_direction(
    coefficients: np.ndarray,
    cartesian_direction: np.ndarray,
    conventional_cell_basis: np.ndarray,
    *,
    max_index: int,
    max_angular_error_deg: float,
) -> CrystallographicDirectionApproximation:
    max_index_value = _validated_max_index(max_index)
    max_error = _finite_nonnegative(
        "max_angular_error_deg",
        max_angular_error_deg,
    )
    basis = _matrix3(conventional_cell_basis, name="conventional_cell_basis")
    coefficients_c = _canonicalize_line(coefficients)
    cartesian_c, cartesian_unit = _unit_cartesian_direction(cartesian_direction)
    best_indices, best_error = _best_low_index_direction(
        basis,
        cartesian_unit,
        max_index=max_index_value,
    )
    accepted = best_error <= max_error
    return CrystallographicDirectionApproximation(
        continuous_coefficients=coefficients_c,
        cartesian_direction=cartesian_c,
        integer_indices=best_indices if accepted else None,
        angular_error_deg=best_error,
        formatted=(_format_integer_direction(best_indices) if accepted else None),
    )


def analyze_principal_directions_in_conventional_cell(
    principal_directions_slab_cart: np.ndarray,
    conventional_cell_basis: np.ndarray,
    slab_to_conventional_cart: np.ndarray,
    *,
    max_index: int = 6,
    max_angular_error_deg: float = 1.0,
) -> PrincipalDirectionMapping:
    """Map resolved slab-frame axes and assess low-index approximations."""
    directions_slab, directions_cart, directions_coeff = _mapped_direction_arrays(
        principal_directions_slab_cart,
        conventional_cell_basis,
        slab_to_conventional_cart,
    )
    approximations = tuple(
        _approximate_crystallographic_direction(
            directions_coeff[:, index],
            directions_cart[:, index],
            conventional_cell_basis,
            max_index=max_index,
            max_angular_error_deg=max_angular_error_deg,
        )
        for index in range(2)
    )
    return PrincipalDirectionMapping(
        directions_slab_cart=directions_slab,
        directions_conventional_cart=directions_cart,
        directions_conventional=directions_coeff,
        approximations=(approximations[0], approximations[1]),
    )


__all__ = [
    "CrystallographicDirectionApproximation",
    "DirectionStatus",
    "PrincipalDirectionMapping",
    "StrainDecomposition",
    "analyze_principal_directions_in_conventional_cell",
    "compute_strain_decomposition",
    "slab_to_conventional_cartesian_map_from_payload",
]
