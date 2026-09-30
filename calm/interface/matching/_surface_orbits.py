"""Surface-cell orbit bundles for the coupled-v2 matching path."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from calm.interface.matching.conditioning import evaluate_condition_admissibility_2d
from calm.exceptions import (
    CanonicalGaussReductionError,
    SurfaceCellHandednessError,
)
from calm.keys.hnf import (
    canonical_hnf_under_pg_with_witness,
    normalize_pg_ops_frozen,
)
from calm.math2d.normal_forms import enumerate_hnf_2d_by_index
from calm.symmetry.reduction import (
    canonical_gauss_reduce_2d,
    oriented_gauss_reduce_2d,
)

from calm.interface.matching._types import SurfaceCellMember2D, SurfaceCellOrbit2D
from calm.interface.matching._utils import _finite_positive_float, _positive_integer


def _strict_bool(name: str, value: object) -> bool:
    if not isinstance(value, (bool, np.bool_)):
        raise TypeError(f"{name} must be a boolean")
    return bool(value)


def _reduction_options(
    values: dict[str, Any] | None,
) -> tuple[dict[str, Any], bool, bool]:
    """Validate controls for the canonical two-dimensional Gauss reducer."""

    options = {} if values is None else dict(values)
    allowed = {
        "tol",
        "det_tol",
        "max_iter",
        "strict_handedness",
        "warn_on_handedness_repair",
    }
    unknown = sorted(set(options) - allowed)
    if unknown:
        raise TypeError(
            "unsupported surface orbit reduction options: " + ", ".join(unknown)
        )

    strict_handedness = _strict_bool(
        "surface orbit reduction strict_handedness",
        options.pop("strict_handedness", False),
    )
    warn_on_handedness_repair = _strict_bool(
        "surface orbit reduction warn_on_handedness_repair",
        options.pop("warn_on_handedness_repair", False),
    )
    if "tol" in options:
        options["tol"] = _finite_positive_float(
            "surface orbit reduction tol", options["tol"]
        )
    if "det_tol" in options:
        options["det_tol"] = _finite_positive_float(
            "surface orbit reduction det_tol", options["det_tol"]
        )
    if "max_iter" in options:
        options["max_iter"] = _positive_integer(
            "surface orbit reduction max_iter", options["max_iter"]
        )
    return options, strict_handedness, warn_on_handedness_repair


def _primitive_basis(value: object) -> np.ndarray:
    primitive = np.asarray(value, dtype=float)
    if primitive.shape != (2, 2):
        raise ValueError("prim_basis must have shape (2, 2)")
    if not np.all(np.isfinite(primitive)):
        raise ValueError("prim_basis must contain only finite values")
    determinant = float(np.linalg.det(primitive))
    if not np.isfinite(determinant) or determinant == 0.0:
        raise ValueError("prim_basis must be nonsingular")
    return primitive


def _symmetrized_gram(basis: np.ndarray) -> np.ndarray:
    gram = basis.T @ basis
    return 0.5 * (gram + gram.T)


def _member_rank(member: SurfaceCellMember2D) -> tuple[object, ...]:
    return (
        float(member.condition_number),
        tuple(int(value) for value in member.H.ravel()),
        tuple(int(value) for value in member.oriented_N.ravel()),
    )


def _float_key(value: float) -> str:
    return float(value).hex()


def _reduction_options_key(options: dict[str, Any]) -> tuple[tuple[str, object], ...]:
    output: list[tuple[str, object]] = []
    for name in sorted(options):
        value = options[name]
        if isinstance(value, int):
            output.append((name, int(value)))
        else:
            output.append((name, _float_key(float(value))))
    return tuple(output)


@dataclass(frozen=True)
class _SurfaceOrbitBuildContext2D:
    """Validated search-scoped state for one surface-orbit catalog."""

    primitive: np.ndarray
    point_group: tuple[np.ndarray, ...]
    condition_limit: float
    reduction_options: dict[str, Any]
    strict_handedness: bool
    warn_on_handedness_repair: bool
    key: tuple[object, ...]


def _prepare_surface_orbit_build_context_2d(
    *,
    prim_basis: np.ndarray,
    PG_ops: Sequence[np.ndarray],
    cond_max: float,
    reduction_kwargs: dict[str, Any] | None,
) -> _SurfaceOrbitBuildContext2D:
    """Validate catalog inputs once and provide an exact reuse key."""

    primitive = _primitive_basis(prim_basis)
    point_group = normalize_pg_ops_frozen(PG_ops)
    condition_limit = _finite_positive_float("cond_max", cond_max)
    options, strict_handedness, warn_on_handedness_repair = _reduction_options(
        reduction_kwargs
    )
    key = (
        tuple(_float_key(value) for value in primitive.ravel()),
        tuple(
            tuple(int(value) for value in operation.ravel())
            for operation in point_group
        ),
        _float_key(condition_limit),
        _reduction_options_key(options),
        strict_handedness,
        warn_on_handedness_repair,
    )
    return _SurfaceOrbitBuildContext2D(
        primitive=primitive,
        point_group=point_group,
        condition_limit=condition_limit,
        reduction_options=options,
        strict_handedness=strict_handedness,
        warn_on_handedness_repair=warn_on_handedness_repair,
        key=key,
    )


def _build_member(
    *,
    primitive: np.ndarray,
    k: int,
    H: np.ndarray,
    point_group: Sequence[np.ndarray],
    condition_limit: float,
    reduction_options: dict[str, Any],
    strict_handedness: bool,
    warn_on_handedness_repair: bool,
) -> tuple[SurfaceCellMember2D | None, str | None]:
    """Build one member and report the rejected stage when applicable."""

    supercell = primitive @ H
    try:
        shape_basis, shape_U, shape_embedding = canonical_gauss_reduce_2d(
            supercell,
            strict_handedness=strict_handedness,
            warn_on_handedness_repair=warn_on_handedness_repair,
            **reduction_options,
        )
        oriented_basis, oriented_U, oriented_embedding = oriented_gauss_reduce_2d(
            supercell,
            **reduction_options,
        )
    except SurfaceCellHandednessError:
        raise
    except (
        CanonicalGaussReductionError,
        FloatingPointError,
        ValueError,
        np.linalg.LinAlgError,
    ):
        return None, "reduction_failed"

    condition_number, admitted = evaluate_condition_admissibility_2d(
        shape_basis,
        cond_max=condition_limit,
    )
    if not admitted:
        return None, "condition_rejected"

    H_integer = np.asarray(H, dtype=int)
    oriented_U_integer = np.asarray(oriented_U, dtype=int)
    oriented_N = H_integer @ oriented_U_integer
    canonicalization = canonical_hnf_under_pg_with_witness(
        oriented_N,
        point_group,
    )
    member = SurfaceCellMember2D(
        k=k,
        H=H_integer,
        shape_basis=np.asarray(shape_basis, dtype=float),
        shape_gram=_symmetrized_gram(shape_basis),
        shape_U=np.asarray(shape_U, dtype=int),
        shape_embedding=np.asarray(shape_embedding, dtype=float),
        oriented_basis=np.asarray(oriented_basis, dtype=float),
        oriented_gram=_symmetrized_gram(oriented_basis),
        oriented_N=oriented_N,
        oriented_U=oriented_U_integer,
        oriented_embedding=np.asarray(oriented_embedding, dtype=float),
        surface_orbit_key=canonicalization.key,
        condition_number=condition_number,
    )
    return member, None


def _verify_orbit_shape(
    members: Sequence[SurfaceCellMember2D],
    *,
    tolerance: float,
) -> None:
    """Require one O(2)-canonical shape Gram throughout an orbit."""

    reference = members[0].shape_gram
    scale = max(1.0, float(np.max(np.abs(reference))))
    for member in members[1:]:
        if not np.allclose(
            member.shape_gram,
            reference,
            rtol=tolerance,
            atol=tolerance * scale,
        ):
            raise RuntimeError(
                "surface orbit members do not share one canonical shape Gram"
            )


def _enumerate_surface_cell_orbits_for_index_prepared(
    *,
    context: _SurfaceOrbitBuildContext2D,
    k: int,
    stats: dict[str, int] | None,
) -> tuple[SurfaceCellOrbit2D, ...]:
    """Enumerate one determinant index from validated search-scoped state."""

    index = _positive_integer("k", k)
    grouped: dict[tuple[int, int, int, int], list[SurfaceCellMember2D]] = {}
    hnf_total = 0
    reduction_failed = 0
    condition_rejected = 0
    for H in enumerate_hnf_2d_by_index(index):
        hnf_total += 1
        member, rejection = _build_member(
            primitive=context.primitive,
            k=index,
            H=H,
            point_group=context.point_group,
            condition_limit=context.condition_limit,
            reduction_options=context.reduction_options,
            strict_handedness=context.strict_handedness,
            warn_on_handedness_repair=context.warn_on_handedness_repair,
        )
        if member is None:
            if rejection == "condition_rejected":
                condition_rejected += 1
            else:
                reduction_failed += 1
            continue
        grouped.setdefault(member.surface_orbit_key, []).append(member)

    tolerance = float(context.reduction_options.get("tol", 1e-12))
    orbits: list[SurfaceCellOrbit2D] = []
    generated_members = 0
    for key in sorted(grouped):
        members = tuple(sorted(grouped[key], key=_member_rank))
        _verify_orbit_shape(members, tolerance=max(100.0 * tolerance, 1e-10))
        generated_members += len(members)
        orbits.append(
            SurfaceCellOrbit2D(
                key=key,
                representative=members[0],
                members=members,
            )
        )

    if stats is not None:
        stats.update(
            {
                "hnf_total": hnf_total,
                "reduction_failed": reduction_failed,
                "condition_rejected": condition_rejected,
                "generated_members": generated_members,
                "orbit_count": len(orbits),
                "symmetry_removed_from_comparison": max(
                    0, generated_members - len(orbits)
                ),
            }
        )
    return tuple(orbits)


def enumerate_surface_cell_orbits_for_index(
    *,
    prim_basis: np.ndarray,
    k: int,
    PG_ops: Sequence[np.ndarray],
    cond_max: float,
    reduction_kwargs: dict[str, Any] | None = None,
    stats: dict[str, int] | None = None,
) -> tuple[SurfaceCellOrbit2D, ...]:
    """Enumerate one determinant index without discarding orbit members."""

    context = _prepare_surface_orbit_build_context_2d(
        prim_basis=prim_basis,
        PG_ops=PG_ops,
        cond_max=cond_max,
        reduction_kwargs=reduction_kwargs,
    )
    return _enumerate_surface_cell_orbits_for_index_prepared(
        context=context,
        k=k,
        stats=stats,
    )


def _build_surface_cell_orbit_index_prepared(
    *,
    context: _SurfaceOrbitBuildContext2D,
    k_max: int,
    stats: dict[int, dict[str, int]] | None = None,
) -> dict[int, tuple[SurfaceCellOrbit2D, ...]]:
    """Build one inclusive orbit index from validated search-scoped state."""

    limit = _positive_integer("k_max", k_max)
    output: dict[int, tuple[SurfaceCellOrbit2D, ...]] = {}
    for index in range(1, limit + 1):
        index_stats: dict[str, int] | None = {} if stats is not None else None
        output[index] = _enumerate_surface_cell_orbits_for_index_prepared(
            context=context,
            k=index,
            stats=index_stats,
        )
        if stats is not None and index_stats is not None:
            stats[index] = index_stats
    return output


def build_surface_cell_orbit_index(
    *,
    prim_basis: np.ndarray,
    k_max: int,
    PG_ops: Sequence[np.ndarray],
    cond_max: float,
    reduction_kwargs: dict[str, Any] | None = None,
    stats: dict[int, dict[str, int]] | None = None,
) -> dict[int, tuple[SurfaceCellOrbit2D, ...]]:
    """Build v2 orbit bundles through one inclusive determinant bound."""

    context = _prepare_surface_orbit_build_context_2d(
        prim_basis=prim_basis,
        PG_ops=PG_ops,
        cond_max=cond_max,
        reduction_kwargs=reduction_kwargs,
    )
    return _build_surface_cell_orbit_index_prepared(
        context=context,
        k_max=k_max,
        stats=stats,
    )
