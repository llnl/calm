"""Geodesic strain partitioning helpers.

This module provides *lightweight* helpers for exploring how interfacial strain
is partitioned between two materials.

Context
-------
In calm, a prototype search yields lattice-matched supercells (a common 2D
interface cell) and the corresponding deformation required to strain each
material into that common cell. A common modeling choice is to *split* that
strain between the two materials, rather than placing 100% of the strain on one
side.

For 2D interface cells, calm represents the in-plane metric as an SPD(2)
(Symmetric Positive Definite 2x2) matrix. The default strain model uses the
affine-invariant geodesic on SPD(2) to interpolate between the two metrics.

This module adds a small utility layer to *scan* a set of partition parameters
(alpha values) and select the best candidate according to a user-supplied
scoring function (e.g., an MLIP energy, or an interfacial energy estimate).

Design notes
------------
- The core scan routine is pure/Python and depends only on numpy plus calm's
  existing strain kernels.
- By default we keep **only the best** result, plus minimal metadata. Full
  traces are optional.
"""

from __future__ import annotations

import inspect
import math
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Sequence

import numpy as np

from calm.interface.refinement._math import geodesic_strain_partition_2d
from calm.interface.refinement.strain import compute_strain_2d
from calm.interface.types import StrainState

ScoreFn = Callable[[StrainState], float]


@dataclass(frozen=True)
class StrainPartitionInplane:
    """Deterministic affine-invariant partitioning to a common in-plane target.

    Parameters
    ----------
    alpha
        Geodesic interpolation parameter in SPD(2). ``alpha=0`` yields slab A's
        in-plane metric, and ``alpha=1`` yields slab B's in-plane metric.
    G_target
        Target 2x2 Gram tensor along the affine-invariant geodesic.
    X
        Deterministic 2x2 in-plane basis for the target metric, chosen via a
        Cholesky lift such that ``X.T @ X == G_target``. By construction ``X`` is
        upper-triangular with positive diagonal entries.
    F_A, F_B
        2x2 deformation gradients mapping each slab's in-plane basis to the
        common target basis: ``F_A = X @ inv(S_A)``, ``F_B = X @ inv(S_B)``.
    side_a_principal_log_strains, side_b_principal_log_strains
        Ordered principal Hencky strains derived from the singular values of
        the actual side-to-target deformation gradients.
    side_a_airm_distance, side_b_airm_distance
        Affine-invariant distances from each side metric to ``G_target``.
        For a 2D Hencky strain vector ``e``, this distance is ``2 * ||e||``.
    """

    alpha: float
    G_target: np.ndarray
    X: np.ndarray
    F_A: np.ndarray
    F_B: np.ndarray
    side_a_principal_log_strains: tuple[float, float]
    side_b_principal_log_strains: tuple[float, float]
    side_a_max_abs_principal_log_strain: float
    side_b_max_abs_principal_log_strain: float
    side_a_airm_distance: float
    side_b_airm_distance: float
    target_basis_gauge: str
    target_basis_gauge_version: int
    target_metric_reconstruction_relative_error: float
    common_target_relative_error: float


def strain_partition_inplane(
    S_A: "np.ndarray",
    S_B: "np.ndarray",
    *,
    alpha: float,
) -> StrainPartitionInplane:
    """Partition in-plane mismatch by interpolating in SPD(2).

    The two right-handed 2D column bases are normalized by one common positive
    length scale before metric, inverse, and spectral operations are evaluated.
    The returned target basis and metric are restored to the physical input
    scale, while the deformation gradients remain dimensionless.

    ``alpha=0`` selects slab A's metric and ``alpha=1`` selects slab B's
    metric. At an endpoint, the corresponding slab has zero stretch but can
    still undergo the deterministic Cholesky-gauge rotation.
    """

    partition = geodesic_strain_partition_2d(
        S_A,
        S_B,
        alpha=alpha,
        eps_spd=1e-14,
    )

    def principal_log_strains(F: np.ndarray) -> tuple[float, float]:
        singular_values = np.linalg.svd(
            np.asarray(F, dtype=float),
            compute_uv=False,
        )
        if (
            singular_values.shape != (2,)
            or not np.all(np.isfinite(singular_values))
            or np.any(singular_values <= 0.0)
        ):
            raise ValueError(
                "Strain-partition deformation gradients must have two "
                "finite positive singular values."
            )
        values = np.sort(np.log(singular_values))
        return (float(values[0]), float(values[1]))

    side_a = principal_log_strains(partition.F_A)
    side_b = principal_log_strains(partition.F_B)

    return StrainPartitionInplane(
        alpha=partition.alpha,
        G_target=partition.target_metric,
        X=partition.target_basis,
        F_A=partition.F_A,
        F_B=partition.F_B,
        side_a_principal_log_strains=side_a,
        side_b_principal_log_strains=side_b,
        side_a_max_abs_principal_log_strain=max(abs(value) for value in side_a),
        side_b_max_abs_principal_log_strain=max(abs(value) for value in side_b),
        side_a_airm_distance=2.0 * float(np.linalg.norm(side_a)),
        side_b_airm_distance=2.0 * float(np.linalg.norm(side_b)),
        target_basis_gauge=partition.target_basis_gauge,
        target_basis_gauge_version=partition.target_basis_gauge_version,
        target_metric_reconstruction_relative_error=(
            partition.target_metric_reconstruction_relative_error
        ),
        common_target_relative_error=partition.common_relative_error,
    )


@dataclass(frozen=True)
class StrainPartitionCandidate:
    """A single strain-partition candidate."""

    alpha: float
    score: float
    strain_state: StrainState


@dataclass(frozen=True)
class StrainPartitionResult:
    """Best strain partition found across a scan."""

    best: StrainPartitionCandidate
    n_evaluated: int
    trace: tuple[tuple[float, float], ...] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def default_alpha_grid(n: int = 11, *, include_endpoints: bool = True) -> list[float]:
    """Return a default alpha grid in [0, 1].

    Parameters
    ----------
    n
        Number of grid points.
    include_endpoints
        If True, include 0 and 1. If False, produce an interior grid.

    Returns
    -------
    list[float]
        Monotone increasing list of alpha values.
    """

    if isinstance(n, bool) or int(n) != n or int(n) <= 0:
        raise ValueError(f"n must be a positive integer; got {n!r}")
    n_int = int(n)

    if include_endpoints:
        vals = np.linspace(0.0, 1.0, n_int)
    else:
        # Interior points only.
        vals = np.linspace(0.0, 1.0, n_int + 2)[1:-1]
    return [float(x) for x in vals]


def _normalize_alphas(alphas: Iterable[float]) -> list[float]:
    out: list[float] = []
    for a in alphas:
        aa = float(a)
        if not math.isfinite(aa) or not 0.0 <= aa <= 1.0:
            raise ValueError(
                f"alpha values must be finite and lie in [0, 1]; got {aa!r}"
            )
        out.append(aa)
    if not out:
        raise ValueError("alphas is empty")

    # Deduplicate while preserving order.
    seen: set[float] = set()
    uniq: list[float] = []
    for a in out:
        if a in seen:
            continue
        seen.add(a)
        uniq.append(a)
    return uniq


def _partition_candidate(
    alpha: float,
    score: float,
    strain_state: StrainState,
) -> StrainPartitionCandidate:
    return StrainPartitionCandidate(
        alpha=float(alpha),
        score=float(score),
        strain_state=strain_state,
    )


def _strictly_better(
    score: float,
    current: StrainPartitionCandidate,
    *,
    minimize: bool,
) -> bool:
    return score < current.score if minimize else score > current.score


def _strain_state_evaluator(
    S_A_3D: np.ndarray,
    S_B_3D: np.ndarray,
    *,
    eps: float,
    symprec: float,
) -> Callable[[float], StrainState]:
    """Build a compatibility-aware strain-state evaluator."""
    params = inspect.signature(compute_strain_2d).parameters

    def evaluate(alpha: float) -> StrainState:
        kwargs: dict[str, Any] = {"alpha": float(alpha)}
        if "eps_spd" in params:
            kwargs["eps_spd"] = float(eps)
        elif "eps" in params:
            kwargs["eps"] = float(eps)
        if "symprec" in params:
            kwargs["symprec"] = float(symprec)
        return compute_strain_2d(  # type: ignore[arg-type]
            S_A_3D,
            S_B_3D,
            **kwargs,
        )

    return evaluate


def _evaluate_partition_candidates(
    alphas: Sequence[float],
    *,
    evaluate: Callable[[float], StrainState],
    score_fn: ScoreFn,
    minimize: bool,
    return_trace: bool,
) -> tuple[StrainPartitionCandidate, list[tuple[float, float]]]:
    """Evaluate a finite alpha sequence with stable first-occurrence ties."""
    best: StrainPartitionCandidate | None = None
    trace: list[tuple[float, float]] = []
    for alpha in alphas:
        strain_state = evaluate(float(alpha))
        score = float(score_fn(strain_state))
        if not math.isfinite(score):
            raise ValueError(
                "score_fn must return a finite scalar for every alpha; "
                f"got {score!r} at alpha={alpha!r}."
            )
        if return_trace:
            trace.append((float(alpha), score))
        candidate = _partition_candidate(float(alpha), score, strain_state)
        if best is None or _strictly_better(score, best, minimize=minimize):
            best = candidate
    if best is None:  # Defensive: normalized alpha sequences are never empty.
        raise RuntimeError("No strain-partition candidates were evaluated")
    return best, trace


def scan_geodesic_strain_partitions(
    S_A_3D: np.ndarray,
    S_B_3D: np.ndarray,
    *,
    alphas: Sequence[float] | None = None,
    score_fn: ScoreFn,
    minimize: bool = True,
    eps: float = 1e-14,
    symprec: float = 1e-5,
    return_trace: bool = False,
    objective_name: str | None = None,
) -> StrainPartitionResult:
    """Scan geodesic strain partitions and select the best candidate.

    Parameters
    ----------
    S_A_3D, S_B_3D
        3x3 surface-cell basis matrices (columns are basis vectors) for the two
        materials in a common reference frame.
    alphas
        Sequence of partition parameters in [0, 1]. If None, uses a default grid.
        Interpretation follows :func:`calm.interface.refinement.strain.compute_strain_2d`:
        alpha=0 uses slab A as the target metric, leaving A unstrained and
        straining B to A; alpha=1 uses slab B as the target metric, leaving B
        unstrained and straining A to B.
    score_fn
        Callable mapping a :class:`~calm.interface.types.StrainState` to a scalar
        score. Lower scores are preferred when ``minimize=True``.
    minimize
        If True (default), select the candidate with minimum score. If False,
        select the maximum.
    eps, symprec
        Numerical parameters forwarded to :func:`compute_strain_2d`.
    return_trace
        If True, include a compact trace of (alpha, score) points.
    objective_name
        Stable name for the supplied scoring objective. If omitted, CALM records
        the callable's qualified name when available. The callable itself is not
        serialized.

    Returns
    -------
    StrainPartitionResult
        Best candidate and (optionally) a compact trace.
    """

    grid_source = "default_11_with_endpoints" if alphas is None else "explicit"
    alphas_n = (
        default_alpha_grid(11, include_endpoints=True)
        if alphas is None
        else _normalize_alphas(alphas)
    )
    if not callable(score_fn):
        raise TypeError("score_fn must be callable")
    if objective_name is None:
        score_name = getattr(score_fn, "__qualname__", None)
        if score_name is None:
            score_name = type(score_fn).__qualname__
    else:
        score_name = str(objective_name).strip()
        if not score_name:
            raise ValueError("objective_name must be nonempty when supplied")

    evaluate = _strain_state_evaluator(
        S_A_3D,
        S_B_3D,
        eps=eps,
        symprec=symprec,
    )
    best, trace = _evaluate_partition_candidates(
        alphas_n,
        evaluate=evaluate,
        score_fn=score_fn,
        minimize=minimize,
        return_trace=return_trace,
    )

    md: dict[str, Any] = {
        "alphas": list(alphas_n),
        "grid_source": grid_source,
        "objective_name": str(score_name),
        "minimize": bool(minimize),
        "selection_direction": "minimum" if minimize else "maximum",
        "tie_policy": "first_occurrence_in_alpha_order",
        "nonfinite_score_policy": "raise",
        "eps": float(eps),
        "symprec": float(symprec),
        "trace_returned": bool(return_trace),
    }

    return StrainPartitionResult(
        best=best,
        n_evaluated=len(alphas_n),
        trace=tuple(trace) if return_trace else None,
        metadata=md,
    )


__all__ = [
    "ScoreFn",
    "StrainPartitionInplane",
    "StrainPartitionCandidate",
    "StrainPartitionResult",
    "default_alpha_grid",
    "strain_partition_inplane",
    "scan_geodesic_strain_partitions",
]
