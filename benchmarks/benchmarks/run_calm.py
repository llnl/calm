"""Detailed benchmark runner for CALM's production coupled matcher.

The rows emitted here are intended for cross-tool plots and diagnostics.  Exact
CALM identity remains the primitive coupled-pair key; ``match_sig`` is retained
only as a common geometric projection for comparison with external tools.

For scaling and audit qualification, use
:mod:`benchmarks.run_coupled_qualification` instead.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import time
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np

from calm.interface.matching.conditioning import (
    DEFAULT_SUPERCELL_CONDITION_LIMIT,
)
from calm.interface.config import PrototypeSearchConfig
from calm.interface.matching.search import search_primitive_match_classes

from .benchmark_pairs import basis_area, default_benchmark_pairs, get_benchmark_pair
from .common_metrics import zm_diagnostics_extended
from .run_coupled_qualification import _calm_version, _slab_from_basis
from .signature import match_signature


DETAIL_SCHEMA = "calm.detailed_match_benchmark/v2"

DETAIL_FIELDS = (
    "schema",
    "method",
    "method_version",
    "implementation",
    "pair",
    "max_area",
    "cond_max",
    "eps_principal_max",
    "tau_max",
    "surface_symmetry_mode",
    "surface_symmetry_A_status",
    "surface_symmetry_A_operation_count",
    "surface_symmetry_B_status",
    "surface_symmetry_B_operation_count",
    "pair_symmetry_policy",
    "correspondence_orientation",
    "identify_material_exchange",
    "kA",
    "kB",
    "areaA",
    "areaB",
    "log_area_ratio",
    "d_cell",
    "d_area",
    "d_shape",
    "eps1",
    "eps2",
    "max_abs_principal_strain",
    "rel_da",
    "rel_db",
    "rel_dgamma",
    "d_gamma_deg",
    "d_gamma_rad",
    "eps_a_log",
    "eps_b_log",
    "eps_shear_approx",
    "gamma_mean_deg",
    "gamma_mean_rad",
    "d_size",
    "score",
    "pair_key_version",
    "pair_key",
    "pair_identity",
    "source_count",
    "source_index_pairs",
    "repeat_indices",
    "sigA",
    "sigB",
    "match_sig",
)


def _kmax_from_max_area(max_area: float, primitive_area: float) -> int:
    maximum = float(max_area)
    area = float(primitive_area)
    if not math.isfinite(maximum) or maximum <= 0.0:
        raise ValueError("max_area must be finite and positive")
    if not math.isfinite(area) or area <= 0.0:
        raise ValueError("primitive area must be finite and positive")
    return max(1, int(math.floor(maximum / area + 1.0e-12)))


def _integer_index(matrix: np.ndarray) -> int:
    array = np.asarray(matrix, dtype=object)
    if array.shape != (2, 2):
        raise ValueError("integer supercell matrix must have shape (2, 2)")
    determinant = int(array[0, 0]) * int(array[1, 1]) - int(array[0, 1]) * int(
        array[1, 0]
    )
    index = abs(determinant)
    if index <= 0:
        raise ValueError("integer supercell matrix must be nonsingular")
    return index


def _resolved_bases(
    pair_name: str,
    *,
    A2: np.ndarray | None,
    B2: np.ndarray | None,
    A: np.ndarray | None,
    B: np.ndarray | None,
) -> tuple[np.ndarray, np.ndarray]:
    basis_a = A2 if A2 is not None else A
    basis_b = B2 if B2 is not None else B
    if (basis_a is None) != (basis_b is None):
        raise TypeError("provide both lattice bases or neither")
    if basis_a is None:
        pair = get_benchmark_pair(pair_name)
        basis_a = pair.A
        basis_b = pair.B
    array_a = np.asarray(basis_a, dtype=float)
    array_b = np.asarray(basis_b, dtype=float)
    if array_a.shape != (2, 2) or array_b.shape != (2, 2):
        raise ValueError("benchmark lattice bases must have shape (2, 2)")
    if not np.all(np.isfinite(array_a)) or not np.all(np.isfinite(array_b)):
        raise ValueError("benchmark lattice bases must be finite")
    return array_a, array_b


def run_calm_for_pair(
    *,
    pair_name: str,
    max_area: float,
    eps_principal_max: float,
    A2: np.ndarray | None = None,
    B2: np.ndarray | None = None,
    A: np.ndarray | None = None,
    B: np.ndarray | None = None,
    cond_max: float = DEFAULT_SUPERCELL_CONDITION_LIMIT,
    tau_max: float | None = None,
    nA_prim: int = 1,
    nB_prim: int = 1,
    N_at_max: int = 5000,
    w_match: float = 0.7,
    sig_tol: float = 1.0e-12,
    sig_scale: float = 1.0e10,
    surface_symmetry_mode: str = "identity_only",
    pair_symmetry_policy: str = "full",
    correspondence_orientation: str = "proper",
    identify_material_exchange: bool = False,
    correspondence_entry_limit: int | None = None,
    debug: bool = False,
) -> list[dict[str, Any]]:
    """Return detailed rows from the authoritative primitive coupled matcher.

    ``tau_max`` is an optional reporting filter on ``|log(A_A/A_B)|``.  It is
    not an alternate matcher or identity policy.  Hard scientific admission is
    controlled by the coupled principal-strain bound.
    """

    basis_a, basis_b = _resolved_bases(
        pair_name,
        A2=A2,
        B2=B2,
        A=A,
        B=B,
    )
    maximum_area = float(max_area)
    area_a_primitive = basis_area(basis_a)
    area_b_primitive = basis_area(basis_b)
    k_max = max(
        _kmax_from_max_area(maximum_area, area_a_primitive),
        _kmax_from_max_area(maximum_area, area_b_primitive),
    )
    if tau_max is not None:
        tau = float(tau_max)
        if not math.isfinite(tau) or tau < 0.0:
            raise ValueError("tau_max must be finite and nonnegative")
    else:
        tau = None

    config = PrototypeSearchConfig(
        k_max=k_max,
        cond_max=float(cond_max),
        eps_principal_max=float(eps_principal_max),
        N_at_max=int(N_at_max),
        w_match=float(w_match),
        surface_symmetry_mode=surface_symmetry_mode,
        pair_symmetry_policy=pair_symmetry_policy,
        correspondence_orientation=correspondence_orientation,
        identify_material_exchange=identify_material_exchange,
        correspondence_entry_limit=correspondence_entry_limit,
    )
    slab_a = _slab_from_basis(basis_a, n_atoms=int(nA_prim))
    slab_b = _slab_from_basis(basis_b, n_atoms=int(nB_prim))

    start = time.perf_counter()
    result = search_primitive_match_classes(slab_a, slab_b, config)
    elapsed = time.perf_counter() - start

    rows: list[dict[str, Any]] = []
    area_tolerance = 1.0e-12 * max(1.0, maximum_area)
    for match_class in result.match_classes:
        representative = match_class.representative
        physical_a = representative.build_R_A @ (
            basis_a @ representative.build_N_A
        )
        physical_b = representative.build_R_B @ (
            basis_b @ representative.build_N_B
        )
        area_a = float(abs(np.linalg.det(physical_a)))
        area_b = float(abs(np.linalg.det(physical_b)))
        if area_a > maximum_area + area_tolerance:
            continue
        if area_b > maximum_area + area_tolerance:
            continue

        log_area_ratio = abs(math.log(area_a / area_b))
        if tau is not None and log_area_ratio > tau + 1.0e-12:
            continue

        strains = representative.ai_strain.principal_strains
        d_cell = representative.ai_strain.d_cell
        d_area = representative.ai_strain.d_area
        d_shape = representative.ai_strain.d_shape
        max_abs_strain = representative.ai_strain.max_abs_principal_strain
        rel_da = representative.zm_strain.rel_da
        rel_db = representative.zm_strain.rel_db
        rel_dgamma = representative.zm_strain.rel_dgamma
        d_gamma_deg = representative.zm_strain.d_gamma_deg
        extended = zm_diagnostics_extended(physical_a, physical_b)
        k_a = _integer_index(representative.build_N_A)
        k_b = _integer_index(representative.build_N_B)
        d_size = representative.d_size
        score = representative.match_score
        signature_a, signature_b, signature_pair = match_signature(
            physical_a,
            physical_b,
            tol=float(sig_tol),
            scale=float(sig_scale),
        )
        pair_key = tuple(int(value) for value in match_class.pair_key)
        identity_policy = representative.pair_identity_policy
        pair_identity = {
            "key_version": int(identity_policy.key_version),
            "primitive_pair_key": list(pair_key),
            "pair_symmetry_policy": identity_policy.pair_symmetry,
            "correspondence_orientation": (
                identity_policy.correspondence_orientation
            ),
            "material_exchange_identified": (
                identity_policy.identify_material_exchange
            ),
        }

        rows.append(
            {
                "schema": DETAIL_SCHEMA,
                "method": "calm_coupled_v2",
                "method_version": _calm_version(),
                "implementation": result.implementation,
                "pair": pair_name,
                "max_area": maximum_area,
                "cond_max": config.cond_max,
                "eps_principal_max": config.eps_principal_max,
                "tau_max": "" if tau is None else tau,
                "surface_symmetry_mode": config.surface_symmetry_mode,
                "surface_symmetry_A_status": (
                    result.surface_symmetry_a.status
                ),
                "surface_symmetry_A_operation_count": (
                    result.surface_symmetry_a.operation_count
                ),
                "surface_symmetry_B_status": (
                    result.surface_symmetry_b.status
                ),
                "surface_symmetry_B_operation_count": (
                    result.surface_symmetry_b.operation_count
                ),
                "pair_symmetry_policy": config.pair_symmetry_policy,
                "correspondence_orientation": config.correspondence_orientation,
                "identify_material_exchange": config.identify_material_exchange,
                "kA": k_a,
                "kB": k_b,
                "areaA": area_a,
                "areaB": area_b,
                "log_area_ratio": log_area_ratio,
                "d_cell": d_cell,
                "d_area": d_area,
                "d_shape": d_shape,
                "eps1": float(strains[0]),
                "eps2": float(strains[1]),
                "max_abs_principal_strain": max_abs_strain,
                "rel_da": rel_da,
                "rel_db": rel_db,
                "rel_dgamma": rel_dgamma,
                "d_gamma_deg": d_gamma_deg,
                "d_gamma_rad": extended["d_gamma_rad"],
                "eps_a_log": extended["eps_a_log"],
                "eps_b_log": extended["eps_b_log"],
                "eps_shear_approx": extended["eps_shear_approx"],
                "gamma_mean_deg": extended["gamma_mean_deg"],
                "gamma_mean_rad": extended["gamma_mean_rad"],
                "d_size": d_size,
                "score": score,
                "pair_key_version": identity_policy.key_version,
                "pair_key": json.dumps(pair_key, separators=(",", ":")),
                "pair_identity": json.dumps(
                    pair_identity, separators=(",", ":"), sort_keys=True
                ),
                "source_count": match_class.source_count,
                "source_index_pairs": json.dumps(
                    sorted(
                        [list(pair) for pair in match_class.source_index_pairs]
                    ),
                    separators=(",", ":"),
                ),
                "repeat_indices": json.dumps(
                    sorted(match_class.repeat_indices), separators=(",", ":")
                ),
                "sigA": signature_a,
                "sigB": signature_b,
                "match_sig": signature_pair,
            }
        )

    rows.sort(
        key=lambda row: (
            float(row["score"]),
            float(row["d_cell"]),
            float(row["d_size"]),
            str(row["pair_key"]),
        )
    )
    if debug:
        print(
            f"[{pair_name} @ max_area={maximum_area:g}] "
            f"classes={len(result.match_classes)} rows={len(rows)} "
            f"time={elapsed:.3f}s (k_max={k_max})"
        )
    return rows


def _write_rows(rows: Iterable[dict[str, Any]], output: str | Path) -> None:
    materialized = list(rows)
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = DETAIL_FIELDS
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="raise")
        writer.writeheader()
        for row in materialized:
            if tuple(row) != DETAIL_FIELDS:
                raise RuntimeError("detailed CALM benchmark row schema mismatch")
            writer.writerow(row)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run detailed benchmarks with CALM's production coupled matcher."
    )
    parser.add_argument("--out", default="results_calm.csv")
    parser.add_argument("--max-areas", default="50,100,200,400")
    parser.add_argument(
        "--pair",
        action="append",
        default=[],
        help="Benchmark pair name; repeat to select multiple pairs.",
    )
    parser.add_argument(
        "--cond-max",
        type=float,
        default=DEFAULT_SUPERCELL_CONDITION_LIMIT,
    )
    parser.add_argument("--eps-principal-max", type=float, default=0.03)
    parser.add_argument(
        "--tau-max",
        type=float,
        default=None,
        help="Optional post-search |log area ratio| reporting filter.",
    )
    parser.add_argument("--nA-prim", type=int, default=1)
    parser.add_argument("--nB-prim", type=int, default=1)
    parser.add_argument("--N-at-max", type=int, default=5000)
    parser.add_argument("--w-match", type=float, default=0.7)
    parser.add_argument("--sig-tol", type=float, default=1.0e-12)
    parser.add_argument("--sig-scale", type=float, default=1.0e10)
    parser.add_argument(
        "--surface-symmetry-mode",
        choices=("discover", "identity_only"),
        default="identity_only",
        help=(
            "Synthetic basis-only cases default to identity_only because "
            "they have no atomistic structure for symmetry discovery."
        ),
    )
    parser.add_argument(
        "--pair-symmetry-policy",
        choices=("proper", "full"),
        default="full",
    )
    parser.add_argument(
        "--correspondence-orientation",
        choices=("proper", "all"),
        default="proper",
    )
    parser.add_argument("--identify-material-exchange", action="store_true")
    parser.add_argument("--correspondence-entry-limit", type=int)
    parser.add_argument("--debug", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    max_areas = [
        float(value.strip())
        for value in str(args.max_areas).split(",")
        if value.strip()
    ]
    if not max_areas:
        raise ValueError("--max-areas must contain at least one value")

    registry = {pair.name: pair for pair in default_benchmark_pairs()}
    selected_names = list(args.pair) or list(registry)
    unknown = sorted(set(selected_names) - set(registry))
    if unknown:
        raise ValueError(f"unknown benchmark pairs: {unknown}")

    rows: list[dict[str, Any]] = []
    for pair_name in selected_names:
        pair = registry[pair_name]
        for maximum_area in max_areas:
            rows.extend(
                run_calm_for_pair(
                    pair_name=pair.name,
                    A2=pair.A,
                    B2=pair.B,
                    max_area=maximum_area,
                    cond_max=args.cond_max,
                    eps_principal_max=args.eps_principal_max,
                    tau_max=args.tau_max,
                    nA_prim=args.nA_prim,
                    nB_prim=args.nB_prim,
                    N_at_max=args.N_at_max,
                    w_match=args.w_match,
                    sig_tol=args.sig_tol,
                    sig_scale=args.sig_scale,
                    surface_symmetry_mode=args.surface_symmetry_mode,
                    pair_symmetry_policy=args.pair_symmetry_policy,
                    correspondence_orientation=(
                        args.correspondence_orientation
                    ),
                    identify_material_exchange=(
                        args.identify_material_exchange
                    ),
                    correspondence_entry_limit=(
                        args.correspondence_entry_limit
                    ),
                    debug=args.debug,
                )
            )
    _write_rows(rows, args.out)
    print(f"Wrote {len(rows)} coupled CALM match records to: {args.out}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
