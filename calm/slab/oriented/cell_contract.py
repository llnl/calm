"""Central geometric contracts for oriented surface blocks and finite slabs.

CALM uses ASE's row-vector cell convention.  The first two vectors define the
oriented surface lattice and must lie in the global ``xy`` plane.  A periodic
bulk-derived precursor may retain an in-plane component in its third vector.
A finite slab admitted for interface construction must instead use a third
boundary vector parallel to global ``z``.

These checks classify geometry; they never repair it.  Construction code must
perform any basis change, boundary re-embedding, or physical deformation
explicitly and retain the corresponding provenance.
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass
from typing import Any

import numpy as np

DEFAULT_SLAB_CELL_RELATIVE_TOLERANCE = 1.0e-10
INTERFACE_READY_SLAB_CELL_POLICY = "interface_ready_slab_cell"
INTERFACE_READY_SLAB_CELL_POLICY_VERSION = 1
SLAB_DEFORMATION_ACCOUNTING_POLICY = "composed_slab_deformation"
SLAB_DEFORMATION_ACCOUNTING_VERSION = 1
INTERFACE_DEFORMATION_ACCOUNTING_INFO_KEY = "calm:slab_deformation_accounting"
INTERFACE_RELAXATION_DEFORMATION_INFO_KEY = (
    "calm:interface_relaxation_deformation"
)
INTERFACE_RELAXATION_DEFORMATION_POLICY = (
    "composed_interface_relaxation_deformation"
)
INTERFACE_RELAXATION_DEFORMATION_VERSION = 1
INTERFACE_DEFORMATION_DIAGNOSTICS_POLICY = "interface_deformation_diagnostics"
INTERFACE_DEFORMATION_DIAGNOSTICS_VERSION = 1


@dataclass(frozen=True)
class SlabCellAssessment:
    """Scale-aware measurements for one row-oriented slab cell."""

    signed_volume: float
    signed_inplane_area: float
    c_normal_component: float
    c_inplane_norm: float
    c_tilt_ratio: float
    relative_tolerance: float

    @property
    def interface_ready(self) -> bool:
        """Whether the third vector is parallel to global Cartesian ``z``."""

        return self.c_tilt_ratio <= self.relative_tolerance


@dataclass(frozen=True)
class SlabDeformationComposition:
    """Construction, interface, and total deformation in one slab gauge.

    ``F_construction`` is the physical deformation already carried by the
    source slab, expressed after the requested in-plane gauge rotation.
    ``F_interface`` is the subsequently applied matching deformation.  Column
    vectors therefore transform according to

    ``x_final = F_interface @ F_construction @ x_pristine``.
    """

    F_construction: np.ndarray
    F_interface: np.ndarray
    F_total: np.ndarray


def _readonly_matrix(value: Any) -> np.ndarray:
    matrix = np.asarray(value, dtype=float).copy()
    matrix.setflags(write=False)
    return matrix


def _finite_deformation_gradient(value: Any, *, name: str) -> np.ndarray:
    deformation = _finite_cell(value, name=name)
    determinant = _safe_determinant(deformation)
    if not np.isfinite(determinant) or determinant <= 0.0:
        raise ValueError(
            f"{name} must have positive finite determinant."
        )
    return deformation


def _orthogonal_gauge(value: Any, *, name: str) -> np.ndarray:
    gauge = _finite_cell(value, name=name)
    tolerance = DEFAULT_SLAB_CELL_RELATIVE_TOLERANCE
    if not np.allclose(
        gauge.T @ gauge,
        np.eye(3),
        atol=tolerance,
        rtol=tolerance,
    ):
        raise ValueError(f"{name} must be orthogonal.")
    determinant = _safe_determinant(gauge)
    if not np.isclose(abs(determinant), 1.0, atol=tolerance, rtol=tolerance):
        raise ValueError(f"{name} must have determinant +1 or -1.")
    expected_z = np.array([0.0, 0.0, 1.0])
    if not np.allclose(gauge[:, 2], expected_z, atol=tolerance, rtol=0.0):
        raise ValueError(f"{name} must preserve global Cartesian z.")
    if not np.allclose(gauge[2, :], expected_z, atol=tolerance, rtol=0.0):
        raise ValueError(f"{name} must preserve global Cartesian z.")
    return gauge


def _proper_rotation(value: Any, *, name: str) -> np.ndarray:
    rotation = _finite_cell(value, name=name)
    tolerance = DEFAULT_SLAB_CELL_RELATIVE_TOLERANCE
    if not np.allclose(
        rotation.T @ rotation,
        np.eye(3),
        atol=tolerance,
        rtol=tolerance,
    ):
        raise ValueError(f"{name} must be orthogonal.")
    determinant = _safe_determinant(rotation)
    if not np.isclose(determinant, 1.0, atol=tolerance, rtol=tolerance):
        raise ValueError(f"{name} must be a proper rotation.")
    return rotation



def _matrix_close(left: Any, right: Any) -> bool:
    """Return a scale-aware exact-current matrix comparison."""

    lhs = np.asarray(left, dtype=float)
    rhs = np.asarray(right, dtype=float)
    scale = max(
        1.0,
        float(np.linalg.norm(lhs, ord=np.inf)),
        float(np.linalg.norm(rhs, ord=np.inf)),
    )
    tolerance = DEFAULT_SLAB_CELL_RELATIVE_TOLERANCE * scale
    return bool(np.allclose(lhs, rhs, atol=tolerance, rtol=0.0))


def _exact_mapping_fields(
    value: Any,
    *,
    name: str,
    fields: set[str],
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping.")
    stored = dict(value)
    missing = sorted(fields - stored.keys())
    unknown = sorted(stored.keys() - fields)
    if missing:
        raise ValueError(f"{name} is missing field(s): " + ", ".join(missing) + ".")
    if unknown:
        raise ValueError(
            f"{name} contains unsupported field(s): " + ", ".join(unknown) + "."
        )
    return stored


def _canonical_accounting_side(value: Any, *, name: str) -> dict[str, Any]:
    stored = _exact_mapping_fields(
        value,
        name=name,
        fields={
            "F_construction_slab",
            "F_interface_slab",
            "F_total_slab",
        },
    )
    construction = _finite_deformation_gradient(
        stored["F_construction_slab"],
        name=f"{name} F_construction_slab",
    )
    interface = _finite_deformation_gradient(
        stored["F_interface_slab"],
        name=f"{name} F_interface_slab",
    )
    total = _finite_deformation_gradient(
        stored["F_total_slab"],
        name=f"{name} F_total_slab",
    )
    expected = interface @ construction
    if not _matrix_close(total, expected):
        raise ValueError(
            f"{name} F_total_slab must equal "
            "F_interface_slab @ F_construction_slab."
        )
    return {
        "F_construction_slab": construction.tolist(),
        "F_interface_slab": interface.tolist(),
        "F_total_slab": total.tolist(),
    }


def canonical_interface_deformation_accounting(value: Any) -> dict[str, Any]:
    """Validate one built-interface deformation-accounting payload."""

    stored = _exact_mapping_fields(
        value,
        name="Interface deformation accounting",
        fields={"policy", "version", "lower", "upper"},
    )
    if stored["policy"] != SLAB_DEFORMATION_ACCOUNTING_POLICY:
        raise ValueError(
            "Unsupported interface deformation-accounting policy "
            f"{stored['policy']!r}."
        )
    version = stored["version"]
    if isinstance(version, bool) or not isinstance(version, int):
        raise TypeError("Interface deformation-accounting version must be an integer.")
    if int(version) != SLAB_DEFORMATION_ACCOUNTING_VERSION:
        raise ValueError(
            "Unsupported interface deformation-accounting version "
            f"{version!r}."
        )
    return {
        "policy": SLAB_DEFORMATION_ACCOUNTING_POLICY,
        "version": SLAB_DEFORMATION_ACCOUNTING_VERSION,
        "lower": _canonical_accounting_side(
            stored["lower"], name="Lower interface deformation accounting"
        ),
        "upper": _canonical_accounting_side(
            stored["upper"], name="Upper interface deformation accounting"
        ),
    }


def _cell_deformation_gradient(initial_cell: Any, final_cell: Any) -> np.ndarray:
    initial = _finite_cell(initial_cell, name="Initial interface cell")
    final = _finite_cell(final_cell, name="Final interface cell")
    require_interface_ready_slab_cell(initial, name="Initial interface cell")
    require_interface_ready_slab_cell(final, name="Final interface cell")
    try:
        inverse = np.linalg.inv(initial.T)
    except np.linalg.LinAlgError as exc:
        raise ValueError("Initial interface cell must be nonsingular.") from exc
    return _finite_deformation_gradient(
        final.T @ inverse,
        name="Interface relaxation deformation gradient",
    )


def canonical_interface_relaxation_deformation(
    value: Any,
    *,
    source_accounting: Mapping[str, Any],
    current_cell: Any | None = None,
) -> dict[str, Any]:
    """Validate cumulative cell-relaxation provenance for one interface."""

    source = canonical_interface_deformation_accounting(source_accounting)
    stored = _exact_mapping_fields(
        value,
        name="Interface relaxation deformation accounting",
        fields={
            "policy",
            "version",
            "source_policy",
            "source_version",
            "cell_mode",
            "composition_count",
            "initial_cell_A",
            "final_cell_A",
            "F_relaxation_interface",
            "lower",
            "upper",
        },
    )
    if stored["policy"] != INTERFACE_RELAXATION_DEFORMATION_POLICY:
        raise ValueError(
            "Unsupported interface relaxation-deformation policy "
            f"{stored['policy']!r}."
        )
    version = stored["version"]
    if isinstance(version, bool) or not isinstance(version, int):
        raise TypeError(
            "Interface relaxation-deformation version must be an integer."
        )
    if int(version) != INTERFACE_RELAXATION_DEFORMATION_VERSION:
        raise ValueError(
            "Unsupported interface relaxation-deformation version "
            f"{version!r}."
        )
    if stored["source_policy"] != source["policy"]:
        raise ValueError("Relaxation provenance source policy is inconsistent.")
    if stored["source_version"] != source["version"]:
        raise ValueError("Relaxation provenance source version is inconsistent.")
    mode = stored["cell_mode"]
    if mode not in {"fixed", "interface_in_plane"}:
        raise ValueError(
            "Interface relaxation-deformation cell_mode must be 'fixed' or "
            "'interface_in_plane'."
        )
    count = stored["composition_count"]
    if isinstance(count, bool) or not isinstance(count, int):
        raise TypeError("Relaxation deformation composition_count must be an integer.")
    if int(count) < 1:
        raise ValueError("Relaxation deformation composition_count must be positive.")

    initial = _finite_cell(stored["initial_cell_A"], name="Initial interface cell")
    final = _finite_cell(stored["final_cell_A"], name="Final interface cell")
    expected_relaxation = _cell_deformation_gradient(initial, final)
    relaxation = _finite_deformation_gradient(
        stored["F_relaxation_interface"],
        name="Interface relaxation deformation gradient",
    )
    if not _matrix_close(relaxation, expected_relaxation):
        raise ValueError(
            "F_relaxation_interface is inconsistent with initial_cell_A and "
            "final_cell_A."
        )
    if mode == "fixed" and not _matrix_close(relaxation, np.eye(3)):
        raise ValueError("Fixed-cell relaxation must record identity cell deformation.")
    if current_cell is not None and not _matrix_close(final, current_cell):
        raise ValueError(
            "Relaxation provenance final_cell_A does not match the persisted cell."
        )

    side_fields = {"F_total_post_relaxation_slab"}
    sides: dict[str, dict[str, Any]] = {}
    for side_name in ("lower", "upper"):
        side = _exact_mapping_fields(
            stored[side_name],
            name=f"{side_name.title()} relaxed deformation accounting",
            fields=side_fields,
        )
        post = _finite_deformation_gradient(
            side["F_total_post_relaxation_slab"],
            name=f"{side_name.title()} F_total_post_relaxation_slab",
        )
        base_total = np.asarray(source[side_name]["F_total_slab"], dtype=float)
        if not _matrix_close(post, relaxation @ base_total):
            raise ValueError(
                f"{side_name.title()} post-relaxation total deformation is "
                "inconsistent with the source accounting."
            )
        sides[side_name] = {"F_total_post_relaxation_slab": post.tolist()}

    return {
        "policy": INTERFACE_RELAXATION_DEFORMATION_POLICY,
        "version": INTERFACE_RELAXATION_DEFORMATION_VERSION,
        "source_policy": source["policy"],
        "source_version": source["version"],
        "cell_mode": mode,
        "composition_count": int(count),
        "initial_cell_A": initial.tolist(),
        "final_cell_A": final.tolist(),
        "F_relaxation_interface": relaxation.tolist(),
        "lower": sides["lower"],
        "upper": sides["upper"],
    }


def canonical_interface_deformation_info(
    info: Any,
    *,
    current_cell: Any | None = None,
    require_source: bool = False,
) -> dict[str, Any]:
    """Validate CALM-owned interface deformation metadata without mutation."""

    if info is None:
        if require_source:
            raise ValueError("Interface deformation accounting is required.")
        return {}
    if not isinstance(info, Mapping):
        raise TypeError("Interface atoms info must be a mapping.")
    source_raw = info.get(INTERFACE_DEFORMATION_ACCOUNTING_INFO_KEY)
    if source_raw is None:
        if require_source:
            raise ValueError("Interface deformation accounting is required.")
        if INTERFACE_RELAXATION_DEFORMATION_INFO_KEY in info:
            raise ValueError(
                "Relaxation deformation accounting requires source accounting."
            )
        return {}
    source = canonical_interface_deformation_accounting(source_raw)
    result = {INTERFACE_DEFORMATION_ACCOUNTING_INFO_KEY: source}
    relaxation_raw = info.get(INTERFACE_RELAXATION_DEFORMATION_INFO_KEY)
    if relaxation_raw is not None:
        result[INTERFACE_RELAXATION_DEFORMATION_INFO_KEY] = (
            canonical_interface_relaxation_deformation(
                relaxation_raw,
                source_accounting=source,
                current_cell=current_cell,
            )
        )
    return result


def _principal_log_strain_diagnostics(
    value: Any,
    *,
    name: str,
) -> dict[str, Any]:
    """Return objective principal-log-strain diagnostics for one deformation."""

    deformation = _finite_deformation_gradient(value, name=name)
    singular_values = np.linalg.svd(deformation, compute_uv=False)
    if np.any(~np.isfinite(singular_values)) or np.any(singular_values <= 0.0):
        raise ValueError(f"{name} must have positive finite singular values.")
    principal = np.sort(np.log(singular_values))
    return {
        "principal_log_strains": principal.tolist(),
        "rms_log_strain": float(np.sqrt(np.mean(principal**2))),
        "max_abs_principal_log_strain": float(np.max(np.abs(principal))),
        "log_volume_ratio": float(np.sum(principal)),
        "volume_ratio": float(np.prod(singular_values)),
    }


def _strain_state_matrix(value: Any, field: str) -> np.ndarray:
    if isinstance(value, Mapping):
        raw = value.get(field)
    else:
        raw = getattr(value, field, None)
    if raw is None:
        raise ValueError(
            f"Interface strain_state is missing required matrix {field}."
        )
    return _finite_deformation_gradient(
        raw,
        name=f"Interface strain_state {field}",
    )


def interface_deformation_diagnostics(
    info: Any,
    *,
    current_cell: Any | None = None,
    strain_state: Any | None = None,
) -> dict[str, Any]:
    """Project validated construction, matching, and total strain diagnostics.

    The returned diagnostics are analysis-only projections. They do not replace
    the exact deformation gradients retained in interface atom provenance.
    ``strain_state``, when supplied, is cross-checked against the incremental
    matching gradients in the atomistic deformation-accounting payload.
    """

    owned = canonical_interface_deformation_info(
        info,
        current_cell=current_cell,
        require_source=True,
    )
    source = owned[INTERFACE_DEFORMATION_ACCOUNTING_INFO_KEY]
    relaxation = owned.get(INTERFACE_RELAXATION_DEFORMATION_INFO_KEY)

    if strain_state is not None:
        lower_matching = _strain_state_matrix(strain_state, "F_A")
        upper_matching = _strain_state_matrix(strain_state, "F_B")
        if not _matrix_close(
            lower_matching,
            source["lower"]["F_interface_slab"],
        ):
            raise ValueError(
                "Interface strain_state F_A does not match the lower incremental "
                "interface deformation accounting."
            )
        if not _matrix_close(
            upper_matching,
            source["upper"]["F_interface_slab"],
        ):
            raise ValueError(
                "Interface strain_state F_B does not match the upper incremental "
                "interface deformation accounting."
            )

    state = "post_relaxation" if relaxation is not None else "pre_relaxation"
    sides: dict[str, dict[str, Any]] = {}
    for side_name in ("lower", "upper"):
        source_side = source[side_name]
        current_total = source_side["F_total_slab"]
        if relaxation is not None:
            current_total = relaxation[side_name][
                "F_total_post_relaxation_slab"
            ]
        sides[side_name] = {
            "construction": _principal_log_strain_diagnostics(
                source_side["F_construction_slab"],
                name=f"{side_name.title()} construction deformation",
            ),
            "incremental_matching": _principal_log_strain_diagnostics(
                source_side["F_interface_slab"],
                name=f"{side_name.title()} incremental matching deformation",
            ),
            "pre_relaxation_total": _principal_log_strain_diagnostics(
                source_side["F_total_slab"],
                name=f"{side_name.title()} pre-relaxation total deformation",
            ),
            "current_total": _principal_log_strain_diagnostics(
                current_total,
                name=f"{side_name.title()} current total deformation",
            ),
        }

    relaxation_gradient = (
        np.eye(3)
        if relaxation is None
        else relaxation["F_relaxation_interface"]
    )
    return {
        "policy": INTERFACE_DEFORMATION_DIAGNOSTICS_POLICY,
        "version": INTERFACE_DEFORMATION_DIAGNOSTICS_VERSION,
        "deformation_state": state,
        "source_policy": source["policy"],
        "source_version": source["version"],
        "lower": sides["lower"],
        "upper": sides["upper"],
        "relaxation_cell": _principal_log_strain_diagnostics(
            relaxation_gradient,
            name="Interface relaxation-cell deformation",
        ),
    }


def record_interface_relaxation_deformation(
    atoms: Any,
    *,
    initial_cell: Any,
    final_cell: Any,
    cell_mode: str,
) -> dict[str, Any] | None:
    """Attach cumulative relaxation deformation while preserving build provenance."""

    info = getattr(atoms, "info", None)
    if info is None:
        return None
    if not isinstance(info, MutableMapping):
        raise TypeError("Relaxed interface atoms info must be a mutable mapping.")
    source_raw = info.get(INTERFACE_DEFORMATION_ACCOUNTING_INFO_KEY)
    if source_raw is None:
        return None
    source = canonical_interface_deformation_accounting(source_raw)
    step = _cell_deformation_gradient(initial_cell, final_cell)
    previous_raw = info.get(INTERFACE_RELAXATION_DEFORMATION_INFO_KEY)
    if previous_raw is None:
        cumulative = step
        origin = _finite_cell(initial_cell, name="Initial interface cell")
        count = 1
        mode = cell_mode
    else:
        previous = canonical_interface_relaxation_deformation(
            previous_raw,
            source_accounting=source,
            current_cell=initial_cell,
        )
        cumulative = step @ np.asarray(
            previous["F_relaxation_interface"], dtype=float
        )
        origin = np.asarray(previous["initial_cell_A"], dtype=float)
        count = int(previous["composition_count"]) + 1
        mode = (
            "interface_in_plane"
            if "interface_in_plane" in {previous["cell_mode"], cell_mode}
            else "fixed"
        )
    final = _finite_cell(final_cell, name="Final interface cell")
    payload = {
        "policy": INTERFACE_RELAXATION_DEFORMATION_POLICY,
        "version": INTERFACE_RELAXATION_DEFORMATION_VERSION,
        "source_policy": source["policy"],
        "source_version": source["version"],
        "cell_mode": mode,
        "composition_count": count,
        "initial_cell_A": origin.tolist(),
        "final_cell_A": final.tolist(),
        "F_relaxation_interface": cumulative.tolist(),
        "lower": {
            "F_total_post_relaxation_slab": (
                cumulative @ np.asarray(source["lower"]["F_total_slab"], dtype=float)
            ).tolist()
        },
        "upper": {
            "F_total_post_relaxation_slab": (
                cumulative @ np.asarray(source["upper"]["F_total_slab"], dtype=float)
            ).tolist()
        },
    }
    canonical = canonical_interface_relaxation_deformation(
        payload,
        source_accounting=source,
        current_cell=final,
    )
    # ``Atoms.info`` is mutable even though its protocol is Mapping-like.
    atoms.info[INTERFACE_RELAXATION_DEFORMATION_INFO_KEY] = canonical
    return canonical


def validate_interface_deformation_provenance(
    atoms: Any,
    *,
    require_source: bool = False,
) -> dict[str, Any]:
    """Validate deformation metadata against the atoms' current cell."""

    info = getattr(atoms, "info", None)
    cell = getattr(atoms, "cell", None)
    if hasattr(cell, "array"):
        cell = cell.array
    return canonical_interface_deformation_info(
        info,
        current_cell=cell,
        require_source=require_source,
    )


def validate_persisted_interface_deformation_payload(
    payload: Mapping[str, Any],
    *,
    require_source: bool = False,
) -> dict[str, Any]:
    """Validate interface deformation metadata in one atoms payload."""

    if not isinstance(payload, Mapping):
        raise TypeError("Persisted atoms payload must be a mapping.")
    owned = canonical_interface_deformation_info(
        payload.get("info"),
        current_cell=payload.get("cell"),
        require_source=require_source,
    )
    canonical = dict(payload)
    if owned:
        info = dict(payload.get("info") or {})
        info.update(owned)
        canonical["info"] = info
    return canonical


def _finite_cell(value: Any, *, name: str) -> np.ndarray:
    cell = np.asarray(value, dtype=float)
    if cell.shape != (3, 3):
        raise ValueError(f"{name} must have shape (3, 3); got {cell.shape}.")
    if not np.all(np.isfinite(cell)):
        raise ValueError(f"{name} must contain only finite values.")
    return cell


def _safe_determinant(value: np.ndarray) -> float:
    """Return a signed determinant without overflow warnings."""

    sign, log_abs = np.linalg.slogdet(value)
    if sign == 0.0:
        return 0.0
    maximum_log = float(np.log(np.finfo(float).max))
    minimum_log = float(np.log(np.nextafter(0.0, 1.0)))
    if log_abs > maximum_log:
        return float(np.copysign(np.inf, sign))
    if log_abs < minimum_log:
        return float(np.copysign(0.0, sign))
    return float(sign * np.exp(log_abs))


def assess_oriented_surface_cell(
    value: Any,
    *,
    name: str = "slab cell",
) -> SlabCellAssessment:
    """Validate and measure an oriented, right-handed surface cell.

    The first two vectors must lie in the global ``xy`` plane and define a
    positive, nonsingular in-plane basis.  The third vector must have a
    positive global-``z`` component.  Its in-plane component is permitted here
    because exact periodic precursors can contain a crystallographic stacking
    translation.
    """

    tolerance = DEFAULT_SLAB_CELL_RELATIVE_TOLERANCE
    cell = _finite_cell(value, name=name)
    a, b, c = cell
    norms = np.linalg.norm(cell, axis=1)
    if np.any(norms <= 0.0):
        raise ValueError(f"{name} vectors must have positive length.")
    normalized = cell / norms[:, None]

    for vector_name, vector, norm in zip(("a", "b"), (a, b), norms[:2], strict=True):
        if abs(float(vector[2])) > tolerance * float(norm):
            raise ValueError(
                f"{name} {vector_name} vector must lie in the global xy plane."
            )

    signed_inplane_area_normalized = float(np.linalg.det(normalized[:2, :2]))
    if signed_inplane_area_normalized <= tolerance:
        raise ValueError(
            f"{name} in-plane basis must be right-handed and nonsingular."
        )

    c_normal = float(c[2])
    if float(normalized[2, 2]) <= tolerance:
        raise ValueError(
            f"{name} third vector must have a positive Cartesian-z component."
        )

    signed_volume_normalized = float(np.linalg.det(normalized))
    if signed_volume_normalized <= tolerance:
        raise ValueError(f"{name} must be right-handed and nonsingular.")

    c_inplane_norm = float(np.linalg.norm(c[:2]))
    c_tilt_ratio = c_inplane_norm / float(norms[2])
    signed_inplane_area = _safe_determinant(cell[:2, :2])
    signed_volume = _safe_determinant(cell)
    return SlabCellAssessment(
        signed_volume=signed_volume,
        signed_inplane_area=signed_inplane_area,
        c_normal_component=c_normal,
        c_inplane_norm=c_inplane_norm,
        c_tilt_ratio=c_tilt_ratio,
        relative_tolerance=tolerance,
    )


def require_interface_ready_slab_cell(
    value: Any,
    *,
    name: str = "slab cell",
) -> SlabCellAssessment:
    """Require a right-handed slab cell with ``c = (0, 0, Lc)`` to tolerance."""

    assessment = assess_oriented_surface_cell(
        value,
        name=name,
    )
    if not assessment.interface_ready:
        raise ValueError(
            f"{name} is not interface-ready: its third vector must be parallel "
            "to global Cartesian z."
        )
    return assessment


def construction_deformation_gradient(
    atoms: Any,
    *,
    name: str,
) -> np.ndarray | None:
    """Return a recorded physical slab-construction deformation, if present.

    Missing transform provenance is permitted for low-level atoms-like inputs.
    When current CALM provenance is present, however, malformed construction
    deformation metadata raises rather than being ignored.
    """

    info = getattr(atoms, "info", None)
    if info is None:
        return None
    if not isinstance(info, Mapping):
        raise TypeError(f"{name} info must be a mapping when present.")

    from calm.slab.oriented.transforms import (
        ORIENTED_SLAB_TRANSFORMS_INFO_KEY,
        from_transforms_payload,
    )

    payload = info.get(ORIENTED_SLAB_TRANSFORMS_INFO_KEY)
    if payload is None:
        return None
    transforms = from_transforms_payload(payload)
    shear = transforms.extra.get("shear_info")
    if shear is None:
        return None
    if not isinstance(shear, Mapping):
        raise TypeError(f"{name} shear_info provenance must be a mapping.")
    if "F_shear_cart" not in shear:
        raise ValueError(
            f"{name} shear_info provenance is missing F_shear_cart."
        )

    return _finite_deformation_gradient(
        shear["F_shear_cart"],
        name=f"{name} construction deformation gradient",
    )


def compose_slab_deformations(
    atoms: Any,
    interface_deformation: Any,
    *,
    gauge_rotation: Any | None = None,
    name: str = "slab",
) -> SlabDeformationComposition:
    """Compose source construction strain with later interface strain.

    The source construction deformation is stored in the slab's original
    Cartesian gauge.  Interface matching may first apply an orthogonal in-plane
    gauge ``G``.  In that gauge the construction deformation is
    ``G @ F_construction @ G.T`` and the total physical map is
    ``F_interface @ G @ F_construction @ G.T``.
    """

    F_interface = _finite_deformation_gradient(
        interface_deformation,
        name=f"{name} interface deformation gradient",
    )
    F_construction_source = construction_deformation_gradient(atoms, name=name)
    if F_construction_source is None:
        F_construction_source = np.eye(3)
    gauge = (
        np.eye(3)
        if gauge_rotation is None
        else _orthogonal_gauge(
            gauge_rotation,
            name=f"{name} in-plane gauge rotation",
        )
    )
    F_construction = gauge @ F_construction_source @ gauge.T
    F_total = F_interface @ F_construction
    _finite_deformation_gradient(
        F_total,
        name=f"{name} total deformation gradient",
    )
    return SlabDeformationComposition(
        F_construction=_readonly_matrix(F_construction),
        F_interface=_readonly_matrix(F_interface),
        F_total=_readonly_matrix(F_total),
    )


def slab_to_conventional_map(
    atoms: Any,
    *,
    gauge_rotation: Any | None = None,
    name: str = "slab",
) -> np.ndarray | None:
    """Return the orthogonal map from a gauged slab frame to conventional.

    Missing exact transform provenance returns ``None`` so legacy low-level
    callers can use the established geometric reference-frame recovery.  A
    present current payload must contain a valid ``R_slab_to_conv`` matrix.
    """

    info = getattr(atoms, "info", None)
    if info is None:
        return None
    if not isinstance(info, Mapping):
        raise TypeError(f"{name} info must be a mapping when present.")

    from calm.slab.oriented.transforms import (
        ORIENTED_SLAB_TRANSFORMS_INFO_KEY,
        from_transforms_payload,
    )

    payload = info.get(ORIENTED_SLAB_TRANSFORMS_INFO_KEY)
    if payload is None:
        return None
    transforms = from_transforms_payload(payload)
    raw = transforms.extra.get("R_slab_to_conv")
    if raw is None:
        construction = construction_deformation_gradient(atoms, name=name)
        if construction is not None and not np.allclose(
            construction,
            np.eye(3),
            atol=DEFAULT_SLAB_CELL_RELATIVE_TOLERANCE,
            rtol=DEFAULT_SLAB_CELL_RELATIVE_TOLERANCE,
        ):
            raise ValueError(
                f"{name} current transform provenance is missing "
                "R_slab_to_conv required for construction-strain accounting."
            )
        return None
    rotation = _proper_rotation(raw, name=f"{name} R_slab_to_conv")
    forward_raw = transforms.extra.get("R_conv_to_slab")
    if forward_raw is None:
        raise ValueError(
            f"{name} current transform provenance is missing R_conv_to_slab."
        )
    forward = _proper_rotation(
        forward_raw,
        name=f"{name} R_conv_to_slab",
    )
    tolerance = DEFAULT_SLAB_CELL_RELATIVE_TOLERANCE
    if not np.allclose(
        rotation,
        forward.T,
        atol=tolerance,
        rtol=tolerance,
    ):
        raise ValueError(
            f"{name} slab/conventional rotations are not mutual inverses."
        )

    construction = construction_deformation_gradient(atoms, name=name)
    if construction is None:
        construction = np.eye(3)
    M_forward_raw = transforms.extra.get("M_conv_to_slab_cart")
    M_reverse_raw = transforms.extra.get("M_slab_to_conv_cart")
    construction_is_identity = np.allclose(
        construction,
        np.eye(3),
        atol=tolerance,
        rtol=tolerance,
    )
    if not construction_is_identity and (
        M_forward_raw is None or M_reverse_raw is None
    ):
        raise ValueError(
            f"{name} current transform provenance requires both Cartesian "
            "maps for non-identity construction deformation."
        )
    if M_forward_raw is not None:
        M_forward = _finite_deformation_gradient(
            M_forward_raw,
            name=f"{name} M_conv_to_slab_cart",
        )
        if not np.allclose(
            M_forward,
            construction @ forward,
            atol=tolerance,
            rtol=tolerance,
        ):
            raise ValueError(
                f"{name} M_conv_to_slab_cart is inconsistent with the "
                "recorded construction deformation and rotation."
            )
    if M_reverse_raw is not None:
        M_reverse = _finite_deformation_gradient(
            M_reverse_raw,
            name=f"{name} M_slab_to_conv_cart",
        )
        expected_reverse = rotation @ np.linalg.inv(construction)
        if not np.allclose(
            M_reverse,
            expected_reverse,
            atol=tolerance,
            rtol=tolerance,
        ):
            raise ValueError(
                f"{name} M_slab_to_conv_cart is inconsistent with the "
                "recorded construction deformation and rotation."
            )
    gauge = (
        np.eye(3)
        if gauge_rotation is None
        else _orthogonal_gauge(
            gauge_rotation,
            name=f"{name} in-plane gauge rotation",
        )
    )
    return rotation @ gauge.T


def require_interface_stackable_slab(
    atoms: Any,
    *,
    name: str = "slab",
) -> SlabCellAssessment:
    """Require interface-ready geometry and valid construction provenance.

    Non-identity physical construction strain is admissible when it is present
    in exact transform provenance.  Downstream builders and strained-bulk
    reference calculations must compose it explicitly with interface strain.
    """

    cell = getattr(atoms, "cell", None)
    if hasattr(cell, "array"):
        cell = cell.array
    assessment = require_interface_ready_slab_cell(
        cell,
        name=f"{name} cell",
    )
    construction_deformation_gradient(atoms, name=name)
    return assessment


__all__ = [
    "DEFAULT_SLAB_CELL_RELATIVE_TOLERANCE",
    "INTERFACE_READY_SLAB_CELL_POLICY",
    "INTERFACE_READY_SLAB_CELL_POLICY_VERSION",
    "INTERFACE_DEFORMATION_ACCOUNTING_INFO_KEY",
    "INTERFACE_DEFORMATION_DIAGNOSTICS_POLICY",
    "INTERFACE_DEFORMATION_DIAGNOSTICS_VERSION",
    "INTERFACE_RELAXATION_DEFORMATION_INFO_KEY",
    "INTERFACE_RELAXATION_DEFORMATION_POLICY",
    "INTERFACE_RELAXATION_DEFORMATION_VERSION",
    "SLAB_DEFORMATION_ACCOUNTING_POLICY",
    "SLAB_DEFORMATION_ACCOUNTING_VERSION",
    "SlabCellAssessment",
    "SlabDeformationComposition",
    "assess_oriented_surface_cell",
    "canonical_interface_deformation_accounting",
    "canonical_interface_deformation_info",
    "canonical_interface_relaxation_deformation",
    "compose_slab_deformations",
    "construction_deformation_gradient",
    "interface_deformation_diagnostics",
    "record_interface_relaxation_deformation",
    "require_interface_ready_slab_cell",
    "require_interface_stackable_slab",
    "slab_to_conventional_map",
    "validate_interface_deformation_provenance",
    "validate_persisted_interface_deformation_payload",
]
