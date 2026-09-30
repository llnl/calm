"""Versioned oriented-slab transformation provenance.

The compact version-1 payload has two explicit validation profiles:

* current ``Atoms.info`` and project records require a complete, validated
  ``construction_controls`` record; and
* standalone version-1 sidecars may omit that field because older CALM
  exports predate it, or preserve a historical version-1 control mapping.

Sidecar compatibility preserves omitted or historical controls as transport
provenance. It never synthesizes current controls, rewrites an old control
vocabulary, or admits an incompatible sidecar as exact-current project state.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping, Tuple, Union, cast

import numpy as np

if TYPE_CHECKING:
    from ase import Atoms

from calm.serialization.scientific import scientific_json_native as _json_native

# Exact-current ambient provenance key used by all slab writers and readers.
ORIENTED_SLAB_TRANSFORMS_INFO_KEY = "calm_oriented_slab_transforms"

# Version 1 remains the standalone sidecar interchange envelope. Its historical
# compatibility profile permits omitted construction controls; current ambient
# and project records apply the stricter profile below.
ORIENTED_SLAB_TRANSFORMS_VERSION = 1

BOUNDED_SURFACE_GAUGE_POLICY = "bounded_surface_gauges"
BOUNDED_SURFACE_GAUGE_POLICY_VERSION = 1


_RESERVED_KEYS = {"version", "hkl", "U"}
_RETIRED_KEYS = {
    "schema_version",
    "miller",
    "miller_index",
    "U_slab_from_conv",
    "U_conv_to_slab",
    "transforms",
    "backend",
}
_CURRENT_CONSTRUCTION_CONTROL_FIELDS = frozenset(
    {
        "policy",
        "policy_version",
        "construction_path",
        "primitive_max_denominator",
        "primitive_reduction_max_iter",
        "stacking_search_radius",
        "stacking_boundary_policy",
        "c_tilt_enabled",
        "c_tilt_search",
        "c_tilt_singular_tolerance",
        "c_tilt_boundary_policy",
    }
)


def _as_int3(value: Any) -> Tuple[int, int, int]:
    """Parse an exact length-three integer sequence."""

    if not isinstance(value, (tuple, list)) or len(value) != 3:
        raise ValueError(f"Expected a length-3 sequence for hkl, got {value!r}")
    if any(
        isinstance(item, bool) or not isinstance(item, (int, np.integer))
        for item in value
    ):
        raise TypeError(f"hkl values must be integers, got {value!r}")
    return tuple(int(item) for item in value)


def _as_matrix3(value: Any, *, name: str = "U") -> np.ndarray:
    """Parse a 3x3 finite float matrix."""

    try:
        arr = np.asarray(value, dtype=float)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{name} must be a numeric 3x3 matrix") from exc
    if arr.shape != (3, 3):
        raise ValueError(f"Expected {name} to have shape (3, 3), got {arr.shape}")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} must contain only finite values")
    return arr


def _positive_int(name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)):
        raise TypeError(f"{name} must be an exact positive integer")
    result = int(value)
    if result <= 0:
        raise ValueError(f"{name} must be positive")
    return result


def _positive_finite_float(name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(
        value,
        (int, float, np.integer, np.floating),
    ):
        raise TypeError(f"{name} must be a positive finite real number")
    result = float(value)
    if not np.isfinite(result) or result <= 0.0:
        raise ValueError(f"{name} must be positive and finite")
    return result


def _transport_construction_controls(value: Any) -> dict[str, Any]:
    """Validate a present sidecar control record without reinterpreting it."""

    if not isinstance(value, Mapping):
        raise TypeError("construction_controls must be a mapping when present")
    normalized = _json_native(
        dict(value),
        path="$.construction_controls",
    )
    if not normalized:
        raise ValueError("construction_controls must not be empty when present")
    return cast(dict[str, Any], normalized)


def canonical_construction_controls(value: Any) -> dict[str, Any]:
    """Validate the complete exact-current bounded-gauge provenance record."""

    stored = _transport_construction_controls(value)
    missing = sorted(_CURRENT_CONSTRUCTION_CONTROL_FIELDS - stored.keys())
    if missing:
        raise ValueError(
            "construction_controls is missing required current field(s): "
            + ", ".join(missing)
        )
    unsupported = sorted(stored.keys() - _CURRENT_CONSTRUCTION_CONTROL_FIELDS)
    if unsupported:
        raise ValueError(
            "construction_controls contains unsupported current field(s): "
            + ", ".join(unsupported)
        )

    if stored["policy"] != BOUNDED_SURFACE_GAUGE_POLICY:
        raise ValueError(
            f"construction_controls.policy must equal {BOUNDED_SURFACE_GAUGE_POLICY!r}"
        )
    policy_version = _positive_int(
        "construction_controls.policy_version",
        stored["policy_version"],
    )
    if policy_version != BOUNDED_SURFACE_GAUGE_POLICY_VERSION:
        raise ValueError(
            "Unsupported construction_controls policy_version "
            f"{policy_version}; expected {BOUNDED_SURFACE_GAUGE_POLICY_VERSION}."
        )
    if stored["construction_path"] != "primitive_bulk":
        raise ValueError(
            "construction_controls.construction_path must equal 'primitive_bulk'"
        )

    stacking_boundary_policy = stored["stacking_boundary_policy"]
    if stacking_boundary_policy != "fail_if_best_candidate_is_on_boundary":
        raise ValueError(
            "construction_controls.stacking_boundary_policy must equal "
            "'fail_if_best_candidate_is_on_boundary'"
        )

    c_tilt_enabled = stored["c_tilt_enabled"]
    if not isinstance(c_tilt_enabled, bool):
        raise TypeError("construction_controls.c_tilt_enabled must be boolean")
    expected_c_tilt_boundary = (
        "fail_if_best_candidate_is_on_boundary" if c_tilt_enabled else "not_applied"
    )
    if stored["c_tilt_boundary_policy"] != expected_c_tilt_boundary:
        raise ValueError(
            "construction_controls.c_tilt_boundary_policy does not match c_tilt_enabled"
        )

    return {
        "policy": BOUNDED_SURFACE_GAUGE_POLICY,
        "policy_version": BOUNDED_SURFACE_GAUGE_POLICY_VERSION,
        "construction_path": "primitive_bulk",
        "primitive_max_denominator": _positive_int(
            "construction_controls.primitive_max_denominator",
            stored["primitive_max_denominator"],
        ),
        "primitive_reduction_max_iter": _positive_int(
            "construction_controls.primitive_reduction_max_iter",
            stored["primitive_reduction_max_iter"],
        ),
        "stacking_search_radius": _positive_int(
            "construction_controls.stacking_search_radius",
            stored["stacking_search_radius"],
        ),
        "stacking_boundary_policy": stacking_boundary_policy,
        "c_tilt_enabled": c_tilt_enabled,
        "c_tilt_search": _positive_int(
            "construction_controls.c_tilt_search",
            stored["c_tilt_search"],
        ),
        "c_tilt_singular_tolerance": _positive_finite_float(
            "construction_controls.c_tilt_singular_tolerance",
            stored["c_tilt_singular_tolerance"],
        ),
        "c_tilt_boundary_policy": expected_c_tilt_boundary,
    }


def bounded_surface_gauge_controls(
    *,
    construction_path: str,
    primitive_max_denominator: int,
    primitive_reduction_max_iter: int,
    stacking_search_radius: int,
    reduce_c_tilt: bool,
    c_tilt_search: int,
    c_tilt_singular_tolerance: float,
) -> dict[str, Any]:
    """Build the one complete exact-current bounded-gauge control record."""

    return canonical_construction_controls(
        {
            "policy": BOUNDED_SURFACE_GAUGE_POLICY,
            "policy_version": BOUNDED_SURFACE_GAUGE_POLICY_VERSION,
            "construction_path": construction_path,
            "primitive_max_denominator": primitive_max_denominator,
            "primitive_reduction_max_iter": primitive_reduction_max_iter,
            "stacking_search_radius": stacking_search_radius,
            "stacking_boundary_policy": ("fail_if_best_candidate_is_on_boundary"),
            "c_tilt_enabled": reduce_c_tilt,
            "c_tilt_search": c_tilt_search,
            "c_tilt_singular_tolerance": c_tilt_singular_tolerance,
            "c_tilt_boundary_policy": (
                "fail_if_best_candidate_is_on_boundary"
                if reduce_c_tilt
                else "not_applied"
            ),
        }
    )


@dataclass(frozen=True)
class OrientedSlabTransforms:
    """Serializable version-1 oriented-slab transform metadata.

    The object is the sidecar transport representation. It may therefore carry
    an older version-1 payload without ``construction_controls``. Exact-current
    ambient and project admission must use :func:`from_transforms_payload`.
    """

    version: int = ORIENTED_SLAB_TRANSFORMS_VERSION
    U: np.ndarray = field(default_factory=lambda: np.eye(3))
    hkl: Tuple[int, int, int] = (0, 0, 1)
    extra: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.version, bool) or not isinstance(
            self.version, (int, np.integer)
        ):
            raise TypeError("version must be an integer")
        version = int(self.version)
        if version != ORIENTED_SLAB_TRANSFORMS_VERSION:
            raise ValueError(
                "Unsupported oriented-slab transforms version "
                f"{version}; expected {ORIENTED_SLAB_TRANSFORMS_VERSION}."
            )
        if not isinstance(self.extra, Mapping):
            raise TypeError("extra must be a mapping")

        object.__setattr__(self, "version", version)
        object.__setattr__(self, "hkl", _as_int3(self.hkl))
        object.__setattr__(self, "U", _as_matrix3(self.U, name="U"))

        forbidden = (_RESERVED_KEYS | _RETIRED_KEYS).intersection(self.extra)
        if forbidden:
            raise ValueError(
                "extra contains reserved or historical keys: "
                + ", ".join(sorted(forbidden))
            )
        extra = cast(
            dict[str, Any],
            _json_native(dict(self.extra), path="$"),
        )
        if "construction_controls" in extra:
            extra["construction_controls"] = _transport_construction_controls(
                extra["construction_controls"]
            )
        object.__setattr__(self, "extra", extra)

    def to_payload(self) -> dict[str, Any]:
        """Return a JSON-compatible version-1 transport payload."""

        return to_transforms_payload(self)

    @property
    def payload(self) -> dict[str, Any]:
        return self.to_payload()

    def to_json(self, *, indent: int | None = 2) -> str:
        """Serialize to JSON."""

        return json.dumps(self.to_payload(), indent=indent, sort_keys=True)

    @property
    def json(self) -> str:
        """Canonical JSON serialization (2-space indented)."""

        return self.to_json(indent=2)

    def write_json(self, path: Union[str, Path], *, overwrite: bool = False) -> Path:
        """Write the version-1 transport payload to a standalone JSON file."""

        p = Path(path)
        if p.exists() and not overwrite:
            raise FileExistsError(f"Refusing to overwrite existing file: {p}")
        p.write_text(self.to_json(indent=2), encoding="utf-8")
        return p

    @classmethod
    def from_json(cls, value: str) -> "OrientedSlabTransforms":
        """Parse one standalone version-1 sidecar-compatible JSON payload."""

        return from_transforms_sidecar_payload(value)

    @classmethod
    def from_json_file(cls, path: Union[str, Path]) -> "OrientedSlabTransforms":
        p = Path(path)
        return cls.from_json(p.read_text(encoding="utf-8"))

    def __eq__(self, other: object) -> bool:  # pragma: no cover
        if not isinstance(other, OrientedSlabTransforms):
            return False
        if (
            self.version != other.version
            or self.hkl != other.hkl
            or self.extra != other.extra
        ):
            return False
        return bool(np.allclose(self.U, other.U))


def to_transforms_payload(transforms: OrientedSlabTransforms) -> dict[str, Any]:
    """Convert a sidecar transport object to a JSON-compatible payload.

    Exact-current ambient and project consumers must subsequently admit the
    payload through :func:`from_transforms_payload`.
    """

    payload: dict[str, Any] = {
        "version": int(transforms.version),
        "hkl": [int(x) for x in transforms.hkl],
        "U": transforms.U.astype(float).tolist(),
    }

    # Include any additional metadata without allowing reserved-key overwrites.
    for k, v in transforms.extra.items():
        if k in _RESERVED_KEYS:
            continue
        payload[k] = _json_native(v)

    return payload


def _parse_transforms_payload(
    payload: Any,
    *,
    require_current_controls: bool,
) -> OrientedSlabTransforms:
    if isinstance(payload, str):
        if not payload.strip():
            raise TypeError("transforms JSON must be a non-empty string")
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid transforms JSON string") from exc
    if not isinstance(payload, Mapping):
        raise ValueError(f"Expected mapping payload, got {type(payload).__name__}")

    m = cast(Mapping[str, Any], payload)
    retired = sorted(_RETIRED_KEYS.intersection(m))
    if retired:
        raise ValueError(
            "Historical oriented-slab transform keys are unsupported: "
            + ", ".join(retired)
        )

    required = {"version", "hkl", "U"}
    missing = sorted(required.difference(m))
    if missing:
        raise ValueError(
            "Transforms payload missing required current keys: " + ", ".join(missing)
        )

    version = m["version"]
    if isinstance(version, bool) or not isinstance(version, (int, np.integer)):
        raise TypeError("Transforms payload version must be an integer")
    version_i = int(version)
    if version_i != ORIENTED_SLAB_TRANSFORMS_VERSION:
        raise ValueError(
            "Unsupported oriented-slab transforms version "
            f"{version_i}; expected {ORIENTED_SLAB_TRANSFORMS_VERSION}."
        )

    extra: dict[str, Any] = {
        key: value for key, value in m.items() if key not in _RESERVED_KEYS
    }
    controls = extra.get("construction_controls")
    if controls is None and "construction_controls" not in extra:
        if require_current_controls:
            raise ValueError(
                "Current oriented-slab transforms payload is missing required "
                "construction_controls provenance."
            )
    elif require_current_controls:
        extra["construction_controls"] = canonical_construction_controls(controls)
    else:
        extra["construction_controls"] = _transport_construction_controls(controls)

    return OrientedSlabTransforms(
        version=version_i,
        U=_as_matrix3(m["U"], name="U"),
        hkl=_as_int3(m["hkl"]),
        extra=extra,
    )


def from_transforms_payload(payload: Any) -> OrientedSlabTransforms:
    """Parse one complete exact-current ambient or project payload.

    Missing, malformed, historical, or unsupported construction provenance is
    rejected. No controls are inferred from current defaults.
    """

    return _parse_transforms_payload(payload, require_current_controls=True)


def from_transforms_sidecar_payload(payload: Any) -> OrientedSlabTransforms:
    """Parse one standalone version-1 sidecar payload.

    The version-1 interchange contract permits ``construction_controls`` to be
    absent. When present, the record must be a nonempty, finite JSON mapping,
    but its historical vocabulary is preserved rather than rewritten as the
    exact-current policy.
    """

    return _parse_transforms_payload(payload, require_current_controls=False)


def put_transforms_payload_in_atoms_info(
    atoms: Atoms,
    payload: Mapping[str, Any],
    *,
    key: str = ORIENTED_SLAB_TRANSFORMS_INFO_KEY,
) -> None:
    """Store a validated exact-current payload in ``atoms.info``."""

    if key != ORIENTED_SLAB_TRANSFORMS_INFO_KEY:
        raise ValueError(
            "Current oriented-slab provenance must use "
            f"{ORIENTED_SLAB_TRANSFORMS_INFO_KEY!r}."
        )
    atoms.info[key] = from_transforms_payload(payload).payload


__all__ = [
    "BOUNDED_SURFACE_GAUGE_POLICY",
    "BOUNDED_SURFACE_GAUGE_POLICY_VERSION",
    "ORIENTED_SLAB_TRANSFORMS_INFO_KEY",
    "ORIENTED_SLAB_TRANSFORMS_VERSION",
    "OrientedSlabTransforms",
    "bounded_surface_gauge_controls",
    "canonical_construction_controls",
    "from_transforms_payload",
    "from_transforms_sidecar_payload",
    "put_transforms_payload_in_atoms_info",
    "to_transforms_payload",
]
