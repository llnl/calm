"""Internal canonicalization helpers for persisted interface refinement.

This module is deliberately dependency-free so public settings, persistence
orchestrators, and contract tests use exactly the same scientific semantics.
It is not part of the public import surface.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Iterable, Mapping, Sequence
from numbers import Integral, Real
from typing import Any


REGISTRY_SEED_DERIVATION = "sha256_utf8_prefix64_mod_2pow31"
REGISTRY_SEED_DERIVATION_VERSION = 1

_STRAIN_METRICS = (
    "gamma_eV_per_A2",
    "potential_energy_density_eV_per_A2",
)


def canonical_strain_metric(value: str) -> str:
    """Return the canonical persisted strain-selection metric."""
    if not isinstance(value, str) or not value.strip():
        raise TypeError("Strain-partition target_metric must be a non-empty string.")
    if value != value.strip():
        raise ValueError(
            "Strain-partition target_metric must not contain surrounding whitespace."
        )
    if value not in _STRAIN_METRICS:
        supported = ", ".join(_STRAIN_METRICS)
        raise ValueError(
            f"Unsupported strain-partition target_metric {value!r}. "
            f"Supported values are: {supported}."
        )
    return value


def canonical_alpha_grid(values: Iterable[float] | None) -> tuple[float, ...]:
    """Validate and deterministically canonicalize a strain alpha grid."""
    if values is None:
        values = (0.0, 0.25, 0.5, 0.75, 1.0)
    normalized: set[float] = set()
    for raw in values:
        if isinstance(raw, bool) or not isinstance(raw, Real):
            raise TypeError("Strain-partition alpha values must be real numbers.")
        value = float(raw)
        if not math.isfinite(value):
            raise ValueError("Strain-partition alpha values must be finite.")
        if not 0.0 <= value <= 1.0:
            raise ValueError("Strain-partition alpha values must lie in [0, 1].")
        normalized.add(value)
    if not normalized:
        raise ValueError("Strain-partition alpha grid must not be empty.")
    return tuple(sorted(normalized))


def select_strain_point(
    points: Sequence[Mapping[str, Any]],
    target_metric: str,
) -> Mapping[str, Any]:
    """Select the finite point minimizing exactly ``target_metric``.

    Objective ties are resolved by the smallest finite alpha and then by input
    order. Authoritative public scans use a sorted canonical alpha grid, so the
    rule is stable even if persisted point order changes.
    """
    metric = canonical_strain_metric(target_metric)
    candidates: list[tuple[float, float, int, Mapping[str, Any]]] = []
    for index, point in enumerate(points):
        raw = point.get(metric)
        if raw is None:
            continue
        if isinstance(raw, bool) or not isinstance(raw, Real):
            raise TypeError(
                f"Strain point {index} metric {metric!r} must be a real number or None."
            )
        value = float(raw)
        if not math.isfinite(value):
            continue
        raw_alpha = point.get("alpha")
        if isinstance(raw_alpha, bool) or not isinstance(raw_alpha, Real):
            raise TypeError(f"Strain point {index} alpha must be a real number.")
        alpha = float(raw_alpha)
        if not math.isfinite(alpha):
            raise ValueError(f"Strain point {index} alpha must be finite.")
        candidates.append((value, alpha, index, point))
    if not candidates:
        raise RuntimeError(
            f"No finite strain-partition values were produced for objective {metric!r}."
        )
    return min(candidates, key=lambda item: item[:3])[3]


def stable_registry_seed(base: str, requested_seed: int | None = None) -> int:
    """Return a cross-process deterministic Monte Carlo seed.

    A user seed remains part of the derivation but is combined with the target
    identity so multi-target runs receive stable, distinct streams.
    """
    if not isinstance(base, str) or not base:
        raise TypeError("Registry seed base must be a non-empty string.")
    if requested_seed is not None:
        if isinstance(requested_seed, bool) or not isinstance(requested_seed, Integral):
            raise TypeError("requested_seed must be an integer or None.")
        if requested_seed < 0:
            raise ValueError("requested_seed must be non-negative.")
    prefix = "derived" if requested_seed is None else f"user:{int(requested_seed)}"
    digest = hashlib.sha256(f"{prefix}:{base}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % (2**31)
