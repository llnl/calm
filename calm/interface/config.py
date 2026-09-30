"""calm.interface.config

Pure configuration dataclasses for the v2 interface pipeline.

These are designed to be:
- easy to serialize (for provenance)
- stable to hash (for UIDs)
- dependency-light
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from numbers import Integral
from typing import Any, Literal

from calm.structure.standardization import (
    nonnegative_finite_float,
    positive_finite_float,
)
from calm.interface.matching.conditioning import DEFAULT_SUPERCELL_CONDITION_LIMIT


PairSymmetryPolicy = Literal["proper", "full"]
CorrespondenceOrientation = Literal["proper", "all"]

DEFAULT_PAIR_SYMMETRY_POLICY: PairSymmetryPolicy = "full"
DEFAULT_CORRESPONDENCE_ORIENTATION: CorrespondenceOrientation = "proper"
DEFAULT_IDENTIFY_MATERIAL_EXCHANGE = False


def _finite_nonnegative_build_float(name: str, value: Any) -> float:
    result = float(value)
    if not math.isfinite(result) or result < 0.0:
        raise ValueError(f"{name} must be finite and non-negative.")
    return result


def _finite_build_translation(value: Any) -> tuple[float, float]:
    try:
        translation = tuple(float(item) for item in value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "InterfaceBuildConfig.translation_frac must contain two finite values."
        ) from exc
    if len(translation) != 2 or not all(math.isfinite(item) for item in translation):
        raise ValueError(
            "InterfaceBuildConfig.translation_frac must contain two finite values."
        )
    return translation


def _nonnegative_build_decimals(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise TypeError(
            "InterfaceBuildConfig.translation_round_decimals must be an integer."
        )
    if value < 0:
        raise ValueError(
            "InterfaceBuildConfig.translation_round_decimals must be non-negative."
        )
    return int(value)


@dataclass(frozen=True)
class PrototypeSearchConfig:
    """Configuration for `find_prototypes`.

    Notes
    -----
    This is the internal configuration boundary for the authoritative
    primitive coupled-pair search. Pair-identity policies are explicit here
    so execution, persistence, and prototype identity use one source of truth.
    """

    # Search envelope
    k_max: int = 10
    cond_max: float = DEFAULT_SUPERCELL_CONDITION_LIMIT
    eps_principal_max: float = 0.15
    N_at_max: int = 1000

    # Objective
    w_match: float = 0.5

    # Output control
    max_results: int = 25

    # Surface-symmetry equivalence policy. Discovery failures are fatal unless
    # the identity-only relation is selected explicitly.
    surface_symmetry_mode: Literal["discover", "identity_only"] = "discover"
    surface_symprec: float = 1e-5
    surface_angle_tolerance: float = 1e-8
    surface_metric_tolerance: float = 1e-5

    # Exact primitive coupled-pair identity policy. These controls are
    # intentionally internal and are not exposed through public settings.
    pair_symmetry_policy: PairSymmetryPolicy = DEFAULT_PAIR_SYMMETRY_POLICY
    correspondence_orientation: CorrespondenceOrientation = (
        DEFAULT_CORRESPONDENCE_ORIENTATION
    )
    identify_material_exchange: bool = DEFAULT_IDENTIFY_MATERIAL_EXCHANGE

    # Optional implementation safety cap.  ``None`` means enumerate the full
    # proven finite correspondence domain for every admitted member pair.
    correspondence_entry_limit: int | None = None

    def __post_init__(self) -> None:
        if self.surface_symmetry_mode not in {"discover", "identity_only"}:
            raise ValueError(
                "surface_symmetry_mode must be 'discover' or 'identity_only'."
            )
        symprec = positive_finite_float(
            "surface_symprec",
            self.surface_symprec,
        )
        angle_tolerance = nonnegative_finite_float(
            "surface_angle_tolerance",
            self.surface_angle_tolerance,
        )
        metric_tolerance = positive_finite_float(
            "surface_metric_tolerance",
            self.surface_metric_tolerance,
        )
        object.__setattr__(self, "surface_symprec", symprec)
        object.__setattr__(self, "surface_angle_tolerance", angle_tolerance)
        object.__setattr__(self, "surface_metric_tolerance", metric_tolerance)

        if self.pair_symmetry_policy not in {"proper", "full"}:
            raise ValueError("pair_symmetry_policy must be 'proper' or 'full'.")
        if self.correspondence_orientation not in {"proper", "all"}:
            raise ValueError("correspondence_orientation must be 'proper' or 'all'.")
        if not isinstance(self.identify_material_exchange, bool):
            raise TypeError("identify_material_exchange must be a boolean.")

        if self.correspondence_entry_limit is not None:
            if isinstance(self.correspondence_entry_limit, bool) or not isinstance(
                self.correspondence_entry_limit,
                Integral,
            ):
                raise TypeError(
                    "correspondence_entry_limit must be a positive integer or None."
                )
            if int(self.correspondence_entry_limit) <= 0:
                raise ValueError(
                    "correspondence_entry_limit must be a positive integer or None."
                )
            object.__setattr__(
                self,
                "correspondence_entry_limit",
                int(self.correspondence_entry_limit),
            )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation of this config.

        This is a UX/helper method intended for examples, provenance logging,
        and stable downstream tooling. The returned mapping is deliberately
        restricted to JSON-friendly primitives.
        """

        d = asdict(self)

        # Normalize tuples to lists for a stable JSON schema.
        for k, v in list(d.items()):
            if isinstance(v, tuple):
                d[k] = list(v)

        return d


@dataclass(frozen=True)
class StrainModel:
    """How strain is applied and partitioned between slabs."""

    method: Literal["ai_gram_geodesic"] = "ai_gram_geodesic"
    partition: Literal["both", "A_only", "B_only"] = "both"

    # Used when partition == "both".
    alpha: float = 0.5

    # Numerical stability knobs (forwarded to compute_strain_2d)
    eps_spd: float = 1e-15
    check_common: bool = True
    common_tol: float = 1e-10

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation of this config.

        This is a UX/helper method intended for examples, provenance logging,
        and stable downstream tooling. The returned mapping is deliberately
        restricted to JSON-friendly primitives.
        """

        d = asdict(self)

        # Normalize tuples to lists for a stable JSON schema.
        for k, v in list(d.items()):
            if isinstance(v, tuple):
                d[k] = list(v)

        return d


@dataclass(frozen=True)
class InterfaceBuildConfig:
    """Build-stage configuration.

    `translation_frac` is an in-plane fractional translation in the strained
    common interface cell basis: t_cart = t1*a + t2*b.
    """

    z_padding: float = 1.5
    vacuum_padding: float | None = None
    translation_frac: tuple[float, float] = (0.0, 0.0)
    translation_round_decimals: int = 8

    def __post_init__(self) -> None:
        z_padding = _finite_nonnegative_build_float(
            "InterfaceBuildConfig.z_padding",
            self.z_padding,
        )
        object.__setattr__(self, "z_padding", z_padding)

        if self.vacuum_padding is not None:
            vacuum = _finite_nonnegative_build_float(
                "InterfaceBuildConfig.vacuum_padding",
                self.vacuum_padding,
            )
            object.__setattr__(self, "vacuum_padding", vacuum)

        translation = _finite_build_translation(self.translation_frac)
        object.__setattr__(self, "translation_frac", translation)
        _nonnegative_build_decimals(self.translation_round_decimals)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation of this config.

        This is a UX/helper method intended for examples, provenance logging,
        and stable downstream tooling. The returned mapping is deliberately
        restricted to JSON-friendly primitives.
        """

        d = asdict(self)

        # Normalize tuples to lists for a stable JSON schema.
        for k, v in list(d.items()):
            if isinstance(v, tuple):
                d[k] = list(v)

        return d


@dataclass(frozen=True)
class EnergyConfig:
    """Energy evaluation configuration.

    Guardrails
    ----------
    strict_reference_frame
        If True, disallow any fallback mapping in get_ortho_map(); raise
        ReferenceFrameError instead.

    warn_on_reference_frame_fallback
        If True, emit ReferenceFrameFallbackWarning when the mapping falls back
        to a less certain method.

    reference_frame_check
        If True, validate that the computed map Q is a proper rotation.

    reference_frame_tol
        Tolerance for orthogonality / determinant checks.
    n_interfaces
        Exact positive number of periodic interfaces represented by the energy
        normalization denominator. The default is two for the standard fully
        periodic bicrystal construction.
    """

    n_interfaces: int = 2
    units: Literal["eV/Ang^2", "J/m^2"] = "eV/Ang^2"
    reference: Literal["strained_bulk"] = "strained_bulk"
    require_stoichiometric: bool = True

    # Optional relaxation controls.
    #
    # These are part of the public UX surface (examples and wrapper helpers),
    # even when the selected energy pathway is a single-point evaluation.
    # Energy backends that support relaxation may choose to consume them.
    fmax: float | None = None
    steps: int | None = None

    # Guardrails / correctness controls
    strict_reference_frame: bool = True
    warn_on_reference_frame_fallback: bool = True
    reference_frame_check: bool = True
    reference_frame_tol: float = 1e-8

    def __post_init__(self) -> None:
        from calm.interface.energy.contract import positive_interface_multiplicity

        multiplicity = positive_interface_multiplicity(self.n_interfaces)
        object.__setattr__(self, "n_interfaces", multiplicity)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation of this config.

        This is a UX/helper method intended for examples, provenance logging,
        and stable downstream tooling. The returned mapping is deliberately
        restricted to JSON-friendly primitives.
        """

        d = asdict(self)

        # Normalize tuples to lists for a stable JSON schema.
        for k, v in list(d.items()):
            if isinstance(v, tuple):
                d[k] = list(v)

        return d


def _positive_registry_steps(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise TypeError("RegistrySearchConfig.n_steps must be an integer.")
    result = int(value)
    if result <= 0:
        raise ValueError("RegistrySearchConfig.n_steps must be positive.")
    return result


def _registry_probability(value: Any) -> float:
    result = float(value)
    if not math.isfinite(result) or not 0.0 <= result <= 1.0:
        raise ValueError(
            "RegistrySearchConfig.p_translate must be finite and in [0, 1]."
        )
    return result


def _optional_registry_seed(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise TypeError("RegistrySearchConfig.seed must be an integer or None.")
    result = int(value)
    if result < 0:
        raise ValueError("RegistrySearchConfig.seed must be non-negative.")
    return result


def _optional_registry_bounds(value: Any) -> tuple[float, float] | None:
    if value is None:
        return None
    if len(value) != 2:
        raise ValueError("RegistrySearchConfig.z_bounds must contain two values.")
    z_min = float(value[0])
    z_max = float(value[1])
    if (
        not math.isfinite(z_min)
        or not math.isfinite(z_max)
        or z_min < 0.0
        or z_min > z_max
    ):
        raise ValueError(
            "RegistrySearchConfig.z_bounds must satisfy "
            "0 <= z_min <= z_max with finite values."
        )
    return z_min, z_max


@dataclass(frozen=True)
class RegistrySearchConfig:
    """Monte Carlo registry search configuration.

    This config is designed for
    :func:`calm.interface.refinement.registry.monte_carlo_registry_search`.

    Notes
    -----
    * ``step_scale`` is a standard deviation in **fractional** in-plane
      translation coordinates ``(t1, t2)``. A proposal is sampled from
      ``N(0, step_scale^2)`` independently for ``t1`` and ``t2``.
    * ``temperature`` has the same units as the objective score. The in-memory
      runner uses total energy in eV; the persisted translation-only workflow
      uses energy density in eV/Å² and its own fixed protocol temperature.
    * ``z_step_scale`` is a standard deviation in **absolute length units**
      (typically Å) for the optional internal-gap coordinate.
    * If ``z_bounds`` is ``None`` **and** ``z_step_scale == 0``, only in-plane
      translation is explored.
    * If ``z_bounds`` is provided (recommended) *or* ``z_step_scale > 0``, both
      translation and ``z_padding`` are explored.
    """

    # Core Monte Carlo parameters
    n_steps: int = 4000
    step_scale: float = 0.15
    temperature: float = 0.05
    seed: int | None = None

    # Optional z-padding exploration
    z_bounds: tuple[float, float] | None = None
    # Default to *disabling* z-moves. In many practical workflows, allowing
    # unbounded z-padding drift can lead to degenerate optima (e.g. decoupled
    # slabs). Enable z-moves explicitly by setting ``z_step_scale > 0`` and/or
    # providing ``z_bounds``.
    z_step_scale: float = 0.0

    # Move-type mixing. Used whenever optional gap moves are enabled.
    p_translate: float = 0.80

    # Trace / provenance
    keep_trace: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "n_steps", _positive_registry_steps(self.n_steps))
        for name in ("step_scale", "temperature", "z_step_scale"):
            value = _finite_nonnegative_build_float(
                f"RegistrySearchConfig.{name}",
                getattr(self, name),
            )
            object.__setattr__(self, name, value)
        object.__setattr__(
            self,
            "p_translate",
            _registry_probability(self.p_translate),
        )
        object.__setattr__(self, "seed", _optional_registry_seed(self.seed))
        object.__setattr__(
            self,
            "z_bounds",
            _optional_registry_bounds(self.z_bounds),
        )
        if not isinstance(self.keep_trace, bool):
            raise TypeError("RegistrySearchConfig.keep_trace must be a bool.")
