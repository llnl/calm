"""Pareto-front analysis helpers.

This module owns dependency-light numerical kernels used by the scientific
search pipeline, persistence, public collections, reporting, and plotting.
The named ``strain_size_pareto`` policy is the authoritative CALM candidate
front. Generic two-dimensional fronts remain available for explicitly named
analysis and visualization tasks.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
from math import isfinite
from numbers import Integral, Real
from typing import Any, Callable, Mapping, Sequence

import numpy as np

STRAIN_SIZE_PARETO_POLICY = "strain_size_pareto"
STRAIN_SIZE_PARETO_VERSION = 1
STRAIN_SIZE_PARETO_OBJECTIVES = ("n_atoms_interface", "d_cell")
STRAIN_SIZE_PARETO_POPULATION_SCOPE = "full_admitted_canonical_pre_rank_pre_truncation"
STRAIN_SIZE_D_CELL_DECIMALS = 12
STRAIN_SIZE_D_CELL_QUANTUM = 10.0 ** (-STRAIN_SIZE_D_CELL_DECIMALS)
AGGREGATE_STRAIN_SIZE_PARETO_POLICY = "aggregate_selected_runs_strain_size_pareto"
AGGREGATE_STRAIN_SIZE_PARETO_SCOPE = "selected_runs_filtered_population"
WORKSPACE_FILTERED_STRAIN_SIZE_PARETO_POLICY = "workspace_filtered_strain_size_pareto"
WORKSPACE_FILTERED_STRAIN_SIZE_PARETO_SCOPE = "selected_run_filtered_population"

Feature = str | Callable[[Any], Any]


@dataclass(frozen=True)
class StrainSizeParetoResult:
    """Authoritative strain--size Pareto membership and policy provenance."""

    mask: np.ndarray
    front_idx: tuple[int, ...]
    front_ids: tuple[str, ...]
    d_cell_keys: tuple[int, ...]
    policy: str = STRAIN_SIZE_PARETO_POLICY
    version: int = STRAIN_SIZE_PARETO_VERSION
    population_scope: str = STRAIN_SIZE_PARETO_POPULATION_SCOPE

    @property
    def population_size(self) -> int:
        return int(self.mask.size)


def _feature_value(point: Any, feature: Feature, default: Any = None) -> Any:
    if callable(feature):
        return feature(point)
    if isinstance(point, Mapping):
        return point.get(feature, default)
    return getattr(point, feature, default)


def canonical_d_cell_key(
    value: Any,
    *,
    decimals: int = STRAIN_SIZE_D_CELL_DECIMALS,
) -> int:
    """Return the transitive integer comparison key for ``d_cell``.

    The finite, non-negative dimensionless mismatch is rounded once using
    decimal half-even rounding. Dominance comparisons use the resulting exact
    integer key; pairwise epsilon comparisons are deliberately avoided because
    they need not define a transitive relation.
    """

    decimals_i = int(decimals)
    if decimals_i < 0:
        raise ValueError("d_cell comparison decimals must be non-negative.")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("d_cell must be a finite non-negative number.") from exc
    if not isfinite(number) or number < 0.0:
        raise ValueError("d_cell must be a finite non-negative number.")

    quantum = Decimal(1).scaleb(-decimals_i)
    try:
        rounded = Decimal(str(number)).quantize(
            quantum,
            rounding=ROUND_HALF_EVEN,
        )
    except InvalidOperation as exc:
        message = "d_cell could not be converted to its comparison key."
        raise ValueError(message) from exc
    return int(rounded.scaleb(decimals_i))


def _exact_nonnegative_atom_count(value: Any) -> int:
    if isinstance(value, (bool, np.bool_)):
        raise TypeError("n_atoms_interface must be an exact non-negative integer.")
    if isinstance(value, Integral):
        result = int(value)
    elif isinstance(value, Real):
        number = float(value)
        if not isfinite(number) or not number.is_integer():
            raise TypeError("n_atoms_interface must be an exact non-negative integer.")
        result = int(number)
    else:
        raise TypeError("n_atoms_interface must be an exact non-negative integer.")
    if result < 0:
        raise ValueError("n_atoms_interface must be non-negative.")
    return result


def _strain_size_objectives(
    points: Sequence[Any],
    *,
    atom_count: Feature,
    d_cell: Feature,
    ids: Feature,
) -> tuple[list[int], list[int], list[str]]:
    atom_counts: list[int] = []
    d_cell_keys: list[int] = []
    point_ids: list[str] = []
    for index, point in enumerate(points):
        atom_counts.append(
            _exact_nonnegative_atom_count(
                _feature_value(point, atom_count, default=None)
            )
        )
        d_cell_keys.append(
            canonical_d_cell_key(_feature_value(point, d_cell, default=None))
        )
        point_ids.append(str(_feature_value(point, ids, default=index)))
    return atom_counts, d_cell_keys, point_ids


def _strain_size_membership(
    atom_counts: Sequence[int],
    d_cell_keys: Sequence[int],
) -> list[bool]:
    """Classify a two-objective minimization front in ``O(n log n)`` time."""

    membership = [True] * len(atom_counts)
    order = sorted(
        range(len(atom_counts)),
        key=lambda index: (atom_counts[index], d_cell_keys[index]),
    )
    best_prior_d_cell: int | None = None
    cursor = 0
    while cursor < len(order):
        first = order[cursor]
        objective = (atom_counts[first], d_cell_keys[first])
        stop = cursor + 1
        while stop < len(order):
            candidate = order[stop]
            if (atom_counts[candidate], d_cell_keys[candidate]) != objective:
                break
            stop += 1

        dominated = best_prior_d_cell is not None and best_prior_d_cell <= objective[1]
        for position in range(cursor, stop):
            membership[order[position]] = not dominated
        if best_prior_d_cell is None:
            best_prior_d_cell = objective[1]
        else:
            best_prior_d_cell = min(best_prior_d_cell, objective[1])
        cursor = stop
    return membership


def strain_size_pareto(
    points: Sequence[Any],
    *,
    atom_count: Feature = "n_atoms_interface",
    d_cell: Feature = "d_cell",
    ids: Feature = "uid",
    policy: str = STRAIN_SIZE_PARETO_POLICY,
    population_scope: str = STRAIN_SIZE_PARETO_POPULATION_SCOPE,
) -> StrainSizeParetoResult:
    """Compute CALM's authoritative strain--size Pareto relation.

    Both exact interface atom count and the canonical ``d_cell`` key are
    minimized. Equal objective pairs do not dominate one another. Returned
    front indices are deterministically sorted by atom count, mismatch key,
    and string identifier, while the mask remains aligned with input order.
    """

    atom_counts, d_cell_keys, point_ids = _strain_size_objectives(
        points,
        atom_count=atom_count,
        d_cell=d_cell,
        ids=ids,
    )
    membership = _strain_size_membership(atom_counts, d_cell_keys)
    front_idx = tuple(
        sorted(
            (index for index, keep in enumerate(membership) if keep),
            key=lambda index: (
                atom_counts[index],
                d_cell_keys[index],
                point_ids[index],
            ),
        )
    )
    return StrainSizeParetoResult(
        mask=np.asarray(membership, dtype=bool),
        front_idx=front_idx,
        front_ids=tuple(point_ids[index] for index in front_idx),
        d_cell_keys=tuple(d_cell_keys),
        policy=str(policy),
        population_scope=str(population_scope),
    )


def strain_size_pareto_metadata(
    *,
    policy: str,
    population_scope: str,
    is_member: bool,
    rank: int | None,
    population_size: int,
    d_cell_key: int,
    version: int = STRAIN_SIZE_PARETO_VERSION,
) -> dict[str, Any]:
    """Return JSON-native provenance for one named strain--size policy."""

    policy_name = str(policy).strip()
    scope_name = str(population_scope).strip()
    if not policy_name or not scope_name:
        raise ValueError("Pareto policy and population scope must be non-empty.")
    return {
        "policy": policy_name,
        "version": int(version),
        "objectives": list(STRAIN_SIZE_PARETO_OBJECTIVES),
        "minimize": [True, True],
        "population_scope": scope_name,
        "population_size": int(population_size),
        "d_cell_decimals": STRAIN_SIZE_D_CELL_DECIMALS,
        "d_cell_quantum": STRAIN_SIZE_D_CELL_QUANTUM,
        "d_cell_key": int(d_cell_key),
        "equal_points_dominate": False,
        "is_member": bool(is_member),
        "rank": None if rank is None else int(rank),
    }


def authoritative_pareto_metadata(
    *,
    is_member: bool,
    rank: int | None,
    population_size: int,
    d_cell_key: int,
    population_scope: str = STRAIN_SIZE_PARETO_POPULATION_SCOPE,
) -> dict[str, Any]:
    """Return provenance for CALM's authoritative full-population policy."""

    return strain_size_pareto_metadata(
        policy=STRAIN_SIZE_PARETO_POLICY,
        population_scope=population_scope,
        is_member=is_member,
        rank=rank,
        population_size=population_size,
        d_cell_key=d_cell_key,
    )


def _has_strain_size_contract_fields(value: Mapping[str, Any]) -> bool:
    expected = {
        "version": STRAIN_SIZE_PARETO_VERSION,
        "d_cell_decimals": STRAIN_SIZE_D_CELL_DECIMALS,
        "equal_points_dominate": False,
    }
    return bool(
        isinstance(value.get("policy"), str)
        and value.get("policy")
        and isinstance(value.get("population_scope"), str)
        and value.get("population_scope")
        and all(
            value.get(key) == expected_value for key, expected_value in expected.items()
        )
        and tuple(value.get("objectives") or ()) == STRAIN_SIZE_PARETO_OBJECTIVES
        and tuple(value.get("minimize") or ()) == (True, True)
    )


def is_strain_size_pareto_metadata(value: Any) -> bool:
    """Return whether ``value`` is a complete named strain--size record."""

    if not isinstance(value, Mapping):
        return False
    if not _has_strain_size_contract_fields(value):
        return False
    try:
        population_size = int(value.get("population_size"))
        d_cell_key = int(value.get("d_cell_key"))
    except (TypeError, ValueError):
        return False
    rank = value.get("rank")
    return bool(
        population_size >= 0
        and d_cell_key >= 0
        and isinstance(value.get("is_member"), bool)
        and (rank is None or isinstance(rank, int))
    )


def is_authoritative_pareto_metadata(value: Any) -> bool:
    """Return whether ``value`` satisfies the authoritative policy contract."""

    return bool(
        is_strain_size_pareto_metadata(value)
        and value.get("policy") == STRAIN_SIZE_PARETO_POLICY
        and value.get("population_scope") == STRAIN_SIZE_PARETO_POPULATION_SCOPE
    )


def _coerce_pareto_arrays(
    x: np.ndarray,
    y: np.ndarray,
    ids: Any,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    x_array = np.asarray(x, dtype=float)
    y_array = np.asarray(y, dtype=float)
    if x_array.ndim != 1 or y_array.ndim != 1:
        raise ValueError("pareto_front_2d_numpy: x and y must be 1D")
    if x_array.shape != y_array.shape:
        raise ValueError("pareto_front_2d_numpy: x and y must have same shape")

    if ids is None:
        ids_array = np.arange(x_array.size)
    else:
        ids_array = np.asarray(ids)
        if ids_array.shape != (x_array.size,):
            raise ValueError("pareto_front_2d_numpy: ids must have same length as x/y")
    return x_array, y_array, ids_array


def _finite_pareto_subset(
    x: np.ndarray,
    y: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    valid = np.isfinite(x) & np.isfinite(y)
    base_indices = np.nonzero(valid)[0]
    return x[valid], y[valid], base_indices


def _pareto_membership_mask(
    x: np.ndarray,
    y: np.ndarray,
    *,
    strict: bool,
) -> np.ndarray:
    membership = np.ones(x.size, dtype=bool)
    for index in range(x.size):
        if not membership[index]:
            continue
        if strict:
            dominated = (
                (x >= x[index]) & (y >= y[index]) & ((x > x[index]) | (y > y[index]))
            )
        else:
            dominated = (x >= x[index]) & (y >= y[index])
        dominated[index] = False
        membership[dominated] = False
    return membership


def _pareto_sort_order(
    pareto_indices: np.ndarray,
    pareto_ids: np.ndarray,
    pareto_x: np.ndarray,
    pareto_y: np.ndarray,
    *,
    ids_were_supplied: bool,
) -> np.ndarray:
    if ids_were_supplied:
        id_key = np.asarray([str(value) for value in pareto_ids], dtype=str)
    else:
        id_key = np.asarray(
            [str(int(index)) for index in pareto_indices],
            dtype=str,
        )
    return np.lexsort((id_key, pareto_y, pareto_x))


def _empty_pareto_front(
    *,
    n_points: int,
    ids_dtype: np.dtype[Any],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    return (
        np.zeros(n_points, dtype=bool),
        np.array([], dtype=int),
        np.array([], dtype=ids_dtype),
        np.array([], dtype=float),
        np.array([], dtype=float),
    )


def _finalize_pareto_front(
    *,
    x: np.ndarray,
    y: np.ndarray,
    ids: np.ndarray,
    pareto_indices: np.ndarray,
    ids_were_supplied: bool,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    pareto_x = x[pareto_indices]
    pareto_y = y[pareto_indices]
    pareto_ids = ids[pareto_indices]
    if pareto_indices.size:
        order = _pareto_sort_order(
            pareto_indices,
            pareto_ids,
            pareto_x,
            pareto_y,
            ids_were_supplied=ids_were_supplied,
        )
        pareto_indices = pareto_indices[order]
        pareto_x = pareto_x[order]
        pareto_y = pareto_y[order]
        pareto_ids = pareto_ids[order]

    mask = np.zeros(x.size, dtype=bool)
    mask[pareto_indices] = True
    return mask, pareto_indices, pareto_ids, pareto_x, pareto_y


def pareto_front_2d_numpy(
    x: np.ndarray,
    y: np.ndarray,
    *,
    ids=None,
    strict: bool = True,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Compute a generic 2D Pareto front for minimization.

    This kernel is retained for explicitly named alternative fronts and
    visualizations. It is not the authoritative CALM candidate membership
    policy; use :func:`strain_size_pareto` for that purpose.
    """

    x_array, y_array, ids_array = _coerce_pareto_arrays(x, y, ids)
    x_valid, y_valid, base_indices = _finite_pareto_subset(
        x_array,
        y_array,
    )
    if base_indices.size == 0:
        return _empty_pareto_front(
            n_points=x_array.size,
            ids_dtype=ids_array.dtype,
        )

    local_mask = _pareto_membership_mask(
        x_valid,
        y_valid,
        strict=strict,
    )
    pareto_indices = base_indices[np.nonzero(local_mask)[0]]
    return _finalize_pareto_front(
        x=x_array,
        y=y_array,
        ids=ids_array,
        pareto_indices=pareto_indices,
        ids_were_supplied=ids is not None,
    )
