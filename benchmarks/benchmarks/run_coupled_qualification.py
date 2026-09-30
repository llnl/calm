"""Reproducible qualification runner for the production coupled-v2 matcher.

This runner is intentionally separate from :mod:`benchmarks.run_slabgen`, which
provides the external SlabGen cross-tool comparison harness.  The output is one
stable CSV row per lattice-pair case and ``k_max`` value.

The equal-square case is an exact algorithmic qualification, not merely a
performance case.  By default it supplies the full eight-operation D4 surface
point group explicitly and checks the frozen manuscript/SI oracle through
``k_max = 30``.  The other synthetic geometry cases deliberately use identity
surface symmetry unless another mode is requested, because they do not contain
atomistic structures from which surface symmetry can be discovered.

Examples
--------
Run a quick four-case smoke qualification::

    python -m benchmarks.run_coupled_qualification \
        --out coupled-smoke.csv --k-max 5

Run the exact square inventory and scaling qualification::

    python -m benchmarks.run_coupled_qualification \
        --out coupled-square.csv --case equal_square --k-max 5 --k-max 30 \
        --measure-memory
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata as importlib_metadata
import json
import platform
import sys
import time
import tracemalloc
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np

from calm.interface.matching._orchestrator import (
    enumerate_coupled_match_classes_core,
)
from calm.interface.matching.audit import CoupledMatchEnumerationAudit
from calm.interface.matching.conditioning import (
    DEFAULT_SUPERCELL_CONDITION_LIMIT,
)
from calm.interface.config import PrototypeSearchConfig
from calm.interface.matching.search import search_primitive_match_classes

from .benchmark_pairs import default_benchmark_pairs
from .qualification_fixtures import (
    FULL_D4_DISCOVERY_BY_INDEX,
    INDEX5_PAIR_ORACLE,
    INDEX5_SURFACE_ORACLE,
    PAIR_KEY_VERSION,
    expected_full_d4_keys,
    full_square_point_group,
)


QUALIFICATION_SCHEMA = "calm.coupled_match_qualification/v2"

CSV_FIELDS = (
    "schema",
    "implementation",
    "case",
    "family",
    "k_max",
    "symmetry_source",
    "surface_symmetry_mode",
    "surface_symmetry_A_status",
    "surface_symmetry_A_operation_count",
    "surface_symmetry_B_status",
    "surface_symmetry_B_operation_count",
    "pair_symmetry_policy",
    "correspondence_orientation",
    "identify_material_exchange",
    "correspondence_entry_limit",
    "pair_key_version",
    "pair_key_sha256",
    "pair_identity_sha256",
    "oracle_status",
    "cond_max",
    "eps_principal_max",
    "N_at_max",
    "w_match",
    "n_atoms_A",
    "n_atoms_B",
    "elapsed_seconds",
    "peak_python_bytes",
    "class_count",
    "source_count_total",
    "source_index_pair_count_total",
    "repeat_index_count_total",
    "min_match_score",
    "min_max_abs_principal_strain",
    "max_primitive_atom_count",
    "surface_A_hnf_generated",
    "surface_A_admitted_members",
    "surface_A_comparison_orbits",
    "surface_B_hnf_generated",
    "surface_B_admitted_members",
    "surface_B_comparison_orbits",
    "area_bound_rejected",
    "index_pairs_scheduled",
    "atom_lower_bound_rejected",
    "orbit_pairs_considered",
    "orbit_prefilter_rejected",
    "orbit_prefilter_inconclusive",
    "orbit_prefilter_admitted",
    "member_pairs_expanded",
    "correspondence_domains",
    "correspondence_column_pairs_tested",
    "unimodular_correspondences_tested",
    "strain_admissible_correspondences",
    "correspondence_limit_failures",
    "unique_source_pairs_primitiveized",
    "nonprimitive_repetitions",
    "primitiveization_cache_hits",
    "primitive_atom_rejected",
    "strict_strain_rejected",
    "candidates_admitted",
    "primitive_classes_created",
    "sources_aggregated_by_pair_key",
    "python_version",
    "numpy_version",
    "calm_version",
    "platform",
)


@dataclass(frozen=True)
class QualificationCase:
    """Named lattice-pair case and its qualification policy."""

    name: str
    family: str
    A: np.ndarray
    B: np.ndarray
    comment: str = ""
    symmetry_fixture: str | None = None
    default_eps_principal_max: float = 0.03


@dataclass(frozen=True)
class _Cell:
    array: np.ndarray


@dataclass(frozen=True)
class _AtomsLike:
    cell: _Cell


@dataclass(frozen=True)
class _Slab:
    atoms: _AtomsLike
    n_atoms: int


def _slab_from_basis(basis: np.ndarray, *, n_atoms: int) -> _Slab:
    basis_array = np.asarray(basis, dtype=float)
    if basis_array.shape != (2, 2):
        raise ValueError("basis must have shape (2, 2)")
    if int(n_atoms) <= 0:
        raise ValueError("n_atoms must be positive")
    cell = np.eye(3, dtype=float)
    cell[:2, :2] = basis_array.T
    cell[2, 2] = 10.0
    return _Slab(atoms=_AtomsLike(cell=_Cell(cell)), n_atoms=int(n_atoms))


def default_qualification_cases() -> tuple[QualificationCase, ...]:
    """Return the synthetic geometry matrix used for coupled qualification."""

    square = QualificationCase(
        name="equal_square",
        family="square",
        A=np.eye(2, dtype=float),
        B=np.eye(2, dtype=float),
        comment=(
            "Equal square lattices with an explicit full-D4 oracle for exact "
            "primitive-class discovery and deduplication."
        ),
        symmetry_fixture="full_square_d4",
        default_eps_principal_max=1.0e-10,
    )
    family_by_name = {
        "rect_small_mismatch": "rectangular",
        "hex_near_degenerate": "hexagonal",
        "oblique_tradeoff": "oblique",
    }
    inherited = tuple(
        QualificationCase(
            name=pair.name,
            family=family_by_name[pair.name],
            A=np.asarray(pair.A, dtype=float),
            B=np.asarray(pair.B, dtype=float),
            comment=pair.comment,
            symmetry_fixture=None,
            default_eps_principal_max=0.03,
        )
        for pair in default_benchmark_pairs()
    )
    return (square, *inherited)


def _calm_version() -> str:
    try:
        return importlib_metadata.version("calm")
    except importlib_metadata.PackageNotFoundError:
        return "source-tree"


def pair_key_digest(pair_keys: Iterable[Sequence[int]]) -> str:
    """Return an order-independent SHA-256 digest of exact primitive keys."""

    normalized = sorted(tuple(int(value) for value in key) for key in pair_keys)
    payload = json.dumps(normalized, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


def _pair_identity_payload(match_class: Any) -> dict[str, Any]:
    policy = match_class.representative.pair_identity_policy
    return {
        "key_version": int(policy.key_version),
        "primitive_pair_key": [int(value) for value in match_class.pair_key],
        "pair_symmetry_policy": str(policy.pair_symmetry),
        "correspondence_orientation": str(policy.correspondence_orientation),
        "material_exchange_identified": bool(policy.identify_material_exchange),
    }


def pair_identity_digest(match_classes: Iterable[Any]) -> str:
    """Digest complete policy-qualified identities, not bare geometric keys."""

    normalized = sorted(
        (_pair_identity_payload(match_class) for match_class in match_classes),
        key=lambda item: (
            item["key_version"],
            tuple(item["primitive_pair_key"]),
            item["pair_symmetry_policy"],
            item["correspondence_orientation"],
            item["material_exchange_identified"],
        ),
    )
    payload = json.dumps(normalized, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


def _optional_min(values: Iterable[float]) -> float | str:
    collected = [float(value) for value in values]
    return min(collected) if collected else ""


def _optional_max(values: Iterable[int]) -> int | str:
    collected = [int(value) for value in values]
    return max(collected) if collected else ""


def _audit_totals(audit: CoupledMatchEnumerationAudit) -> dict[str, int]:
    audit.validate()
    surface_a = audit.surface_A.totals()
    surface_b = audit.surface_B.totals()
    pairs = audit.pairs.totals()
    return {
        "surface_A_hnf_generated": surface_a["hnf_generated"],
        "surface_A_admitted_members": surface_a["admitted_members"],
        "surface_A_comparison_orbits": surface_a["comparison_orbits"],
        "surface_B_hnf_generated": surface_b["hnf_generated"],
        "surface_B_admitted_members": surface_b["admitted_members"],
        "surface_B_comparison_orbits": surface_b["comparison_orbits"],
        **{name: pairs[name] for name in audit.pairs._COUNT_NAMES},
    }


def _run_search(
    case: QualificationCase,
    *,
    slab_a: _Slab,
    slab_b: _Slab,
    config: PrototypeSearchConfig,
    requested_surface_symmetry_mode: str,
) -> tuple[
    tuple[Any, ...],
    CoupledMatchEnumerationAudit,
    str,
    str,
    str,
    int,
    str,
    int,
]:
    use_case_fixture = (
        requested_surface_symmetry_mode == "case_default"
        and case.symmetry_fixture == "full_square_d4"
    )
    if use_case_fixture:
        group = full_square_point_group()
        audit = CoupledMatchEnumerationAudit.empty(config.k_max)
        classes = tuple(
            enumerate_coupled_match_classes_core(
                slab_a,
                slab_b,
                k_max=config.k_max,
                cond_max=config.cond_max,
                w_match=config.w_match,
                eps_principal_max=config.eps_principal_max,
                N_at_max=config.N_at_max,
                surface_symprec=config.surface_symprec,
                surface_angle_tolerance=config.surface_angle_tolerance,
                surface_metric_tolerance=config.surface_metric_tolerance,
                pair_symmetry_policy=config.pair_symmetry_policy,
                correspondence_orientation=config.correspondence_orientation,
                identify_material_exchange=config.identify_material_exchange,
                correspondence_entry_limit=config.correspondence_entry_limit,
                point_group_A=group,
                point_group_B=group,
                audit=audit,
            )
        )
        return (
            classes,
            audit,
            audit.implementation,
            "full_square_d4",
            "explicit_fixture",
            len(group),
            "explicit_fixture",
            len(group),
        )

    resolved_mode = (
        "identity_only"
        if requested_surface_symmetry_mode == "case_default"
        else requested_surface_symmetry_mode
    )
    resolved_config = PrototypeSearchConfig(
        **{
            **config.to_dict(),
            "surface_symmetry_mode": resolved_mode,
        }
    )
    result = search_primitive_match_classes(slab_a, slab_b, resolved_config)
    audit = result.enumeration_audit
    if audit is None:
        raise RuntimeError("authoritative coupled search did not return an audit")
    provenance_a = result.surface_symmetry_a
    provenance_b = result.surface_symmetry_b
    return (
        tuple(result.match_classes),
        audit,
        result.implementation,
        resolved_mode,
        provenance_a.status,
        provenance_a.operation_count,
        provenance_b.status,
        provenance_b.operation_count,
    )


def _square_oracle_applicability(
    case: QualificationCase,
    *,
    k_max: int,
    symmetry_source: str,
    config: PrototypeSearchConfig,
    n_atoms_A: int,
    n_atoms_B: int,
) -> str | None:
    if case.name != "equal_square":
        return "not_applicable_non_square_case"
    if symmetry_source != "full_square_d4":
        return "not_applicable_without_explicit_full_d4"
    if k_max > 30:
        return "not_applicable_above_frozen_k30_inventory"
    if config.pair_symmetry_policy != "full":
        return "not_applicable_pair_symmetry_policy"
    if config.correspondence_orientation != "proper":
        return "not_applicable_correspondence_orientation"
    if config.identify_material_exchange:
        return "not_applicable_material_exchange"
    if config.eps_principal_max > 1.0e-10:
        return "not_applicable_nonexact_strain_tolerance"
    if n_atoms_A != 1 or n_atoms_B != 1:
        return "not_applicable_nonunit_atom_weights"
    if config.N_at_max < 2 * k_max:
        return "not_applicable_atom_limit"
    if (
        config.correspondence_entry_limit is not None
        and config.correspondence_entry_limit < 100
    ):
        return "not_applicable_correspondence_limit"
    return None


def _validate_square_oracle(
    classes: Sequence[Any],
    audit: CoupledMatchEnumerationAudit,
    *,
    k_max: int,
) -> None:
    expected_keys = set(expected_full_d4_keys(k_max))
    by_key = {tuple(match_class.pair_key): match_class for match_class in classes}
    if set(by_key) != expected_keys:
        raise RuntimeError(
            "equal-square full-D4 primitive-class inventory mismatch: "
            f"expected={sorted(expected_keys)}, observed={sorted(by_key)}"
        )

    expected_discoveries = {
        key: first_index
        for first_index, key in FULL_D4_DISCOVERY_BY_INDEX
        if first_index <= k_max
    }
    observed_discoveries = {
        key: min(
            max(int(k_a), int(k_b))
            for k_a, k_b in by_key[key].source_index_pairs
        )
        for key in by_key
    }
    if observed_discoveries != expected_discoveries:
        raise RuntimeError(
            "equal-square full-D4 first-discovery mismatch: "
            f"expected={expected_discoveries}, observed={observed_discoveries}"
        )

    if k_max >= 5:
        for surface_name, surface_audit in (
            ("surface_A", audit.surface_A),
            ("surface_B", audit.surface_B),
        ):
            observed_surface = surface_audit.rows(cumulative=False)[4]
            if observed_surface != INDEX5_SURFACE_ORACLE:
                raise RuntimeError(
                    f"equal-square index-five {surface_name} funnel mismatch: "
                    f"expected={INDEX5_SURFACE_ORACLE}, "
                    f"observed={observed_surface}"
                )

        observed_pairs = audit.pairs.rows(cumulative=False)[4]
        for name, expected in INDEX5_PAIR_ORACLE.items():
            if observed_pairs[name] != expected:
                raise RuntimeError(
                    "equal-square index-five pair funnel mismatch for "
                    f"{name}: expected={expected}, observed={observed_pairs[name]}"
                )
        if observed_pairs["nonprimitive_repetitions"] <= 0:
            raise RuntimeError(
                "equal-square index-five oracle expected nonprimitive repetitions"
            )


def run_qualification_case(
    case: QualificationCase,
    *,
    k_max: int,
    cond_max: float = DEFAULT_SUPERCELL_CONDITION_LIMIT,
    eps_principal_max: float | None = None,
    N_at_max: int = 5000,
    w_match: float = 0.5,
    n_atoms_A: int = 1,
    n_atoms_B: int = 1,
    surface_symmetry_mode: str = "case_default",
    pair_symmetry_policy: str = "full",
    correspondence_orientation: str = "proper",
    identify_material_exchange: bool = False,
    correspondence_entry_limit: int | None = None,
    measure_memory: bool = False,
) -> dict[str, Any]:
    """Run one coupled-v2 case and validate any applicable frozen oracle."""

    resolved_eps = (
        case.default_eps_principal_max
        if eps_principal_max is None
        else float(eps_principal_max)
    )
    config_mode = (
        "identity_only"
        if surface_symmetry_mode == "case_default"
        else surface_symmetry_mode
    )
    config = PrototypeSearchConfig(
        k_max=int(k_max),
        cond_max=float(cond_max),
        eps_principal_max=resolved_eps,
        N_at_max=int(N_at_max),
        w_match=float(w_match),
        surface_symmetry_mode=config_mode,
        pair_symmetry_policy=pair_symmetry_policy,
        correspondence_orientation=correspondence_orientation,
        identify_material_exchange=identify_material_exchange,
        correspondence_entry_limit=correspondence_entry_limit,
    )
    slab_a = _slab_from_basis(case.A, n_atoms=n_atoms_A)
    slab_b = _slab_from_basis(case.B, n_atoms=n_atoms_B)

    if measure_memory:
        tracemalloc.start()
    start = time.perf_counter()
    try:
        (
            classes,
            audit,
            implementation,
            symmetry_source,
            symmetry_a_status,
            symmetry_a_count,
            symmetry_b_status,
            symmetry_b_count,
        ) = _run_search(
            case,
            slab_a=slab_a,
            slab_b=slab_b,
            config=config,
            requested_surface_symmetry_mode=surface_symmetry_mode,
        )
    finally:
        elapsed = time.perf_counter() - start
        if measure_memory:
            _current, peak_python_bytes = tracemalloc.get_traced_memory()
            tracemalloc.stop()
        else:
            peak_python_bytes = ""

    oracle_status = _square_oracle_applicability(
        case,
        k_max=config.k_max,
        symmetry_source=symmetry_source,
        config=config,
        n_atoms_A=slab_a.n_atoms,
        n_atoms_B=slab_b.n_atoms,
    )
    if oracle_status is None:
        _validate_square_oracle(classes, audit, k_max=config.k_max)
        oracle_status = "pass"

    representatives = [match_class.representative for match_class in classes]
    identity_versions = {
        int(representative.pair_identity_policy.key_version)
        for representative in representatives
    }
    if len(identity_versions) > 1:
        raise RuntimeError(
            f"qualification population mixes pair-key versions: {identity_versions}"
        )
    pair_key_version = next(iter(identity_versions), PAIR_KEY_VERSION)

    row: dict[str, Any] = {
        "schema": QUALIFICATION_SCHEMA,
        "implementation": implementation,
        "case": case.name,
        "family": case.family,
        "k_max": config.k_max,
        "symmetry_source": symmetry_source,
        "surface_symmetry_mode": (
            "explicit_fixture"
            if symmetry_source == "full_square_d4"
            else config.surface_symmetry_mode
        ),
        "surface_symmetry_A_status": symmetry_a_status,
        "surface_symmetry_A_operation_count": symmetry_a_count,
        "surface_symmetry_B_status": symmetry_b_status,
        "surface_symmetry_B_operation_count": symmetry_b_count,
        "pair_symmetry_policy": config.pair_symmetry_policy,
        "correspondence_orientation": config.correspondence_orientation,
        "identify_material_exchange": config.identify_material_exchange,
        "correspondence_entry_limit": (
            ""
            if config.correspondence_entry_limit is None
            else config.correspondence_entry_limit
        ),
        "pair_key_version": pair_key_version,
        "pair_key_sha256": pair_key_digest(
            match_class.pair_key for match_class in classes
        ),
        "pair_identity_sha256": pair_identity_digest(classes),
        "oracle_status": oracle_status,
        "cond_max": config.cond_max,
        "eps_principal_max": config.eps_principal_max,
        "N_at_max": config.N_at_max,
        "w_match": config.w_match,
        "n_atoms_A": slab_a.n_atoms,
        "n_atoms_B": slab_b.n_atoms,
        "elapsed_seconds": elapsed,
        "peak_python_bytes": peak_python_bytes,
        "class_count": len(classes),
        "source_count_total": sum(
            match_class.source_count for match_class in classes
        ),
        "source_index_pair_count_total": sum(
            len(match_class.source_index_pairs) for match_class in classes
        ),
        "repeat_index_count_total": sum(
            len(match_class.repeat_indices) for match_class in classes
        ),
        "min_match_score": _optional_min(
            representative.match_score for representative in representatives
        ),
        "min_max_abs_principal_strain": _optional_min(
            representative.ai_strain.max_abs_principal_strain
            for representative in representatives
        ),
        "max_primitive_atom_count": _optional_max(
            representative.atom_count for representative in representatives
        ),
        **_audit_totals(audit),
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "calm_version": _calm_version(),
        "platform": platform.platform(),
    }
    if tuple(row) != CSV_FIELDS:
        missing = [name for name in CSV_FIELDS if name not in row]
        extra = [name for name in row if name not in CSV_FIELDS]
        raise RuntimeError(
            f"qualification row schema mismatch: missing={missing}, extra={extra}"
        )
    return row


def write_qualification_csv(
    rows: Iterable[dict[str, Any]],
    output: str | Path,
) -> None:
    """Write qualification rows using the frozen column order."""

    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="raise")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _selected_cases(names: Sequence[str]) -> tuple[QualificationCase, ...]:
    registry = {case.name: case for case in default_qualification_cases()}
    if not names:
        return tuple(registry.values())
    unknown = sorted(set(names) - set(registry))
    if unknown:
        known = ", ".join(sorted(registry))
        raise ValueError(f"unknown qualification cases {unknown}; known: {known}")
    return tuple(registry[name] for name in names)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the production coupled-v2 matching qualification matrix."
    )
    parser.add_argument("--out", required=True, help="Destination CSV path.")
    parser.add_argument(
        "--case",
        action="append",
        default=[],
        help="Case name; repeat to select multiple cases. Defaults to all.",
    )
    parser.add_argument(
        "--k-max",
        action="append",
        type=int,
        required=True,
        help="Maximum HNF index; repeat for a scaling series.",
    )
    parser.add_argument(
        "--cond-max",
        type=float,
        default=DEFAULT_SUPERCELL_CONDITION_LIMIT,
    )
    parser.add_argument(
        "--eps-principal-max",
        type=float,
        default=None,
        help=(
            "Override the case default. Equal-square defaults to 1e-10 for the "
            "exact oracle; other cases default to 0.03."
        ),
    )
    parser.add_argument("--N-at-max", type=int, default=5000)
    parser.add_argument("--w-match", type=float, default=0.5)
    parser.add_argument("--n-atoms-A", type=int, default=1)
    parser.add_argument("--n-atoms-B", type=int, default=1)
    parser.add_argument(
        "--surface-symmetry-mode",
        choices=("case_default", "discover", "identity_only"),
        default="case_default",
        help=(
            "case_default uses explicit full D4 for equal_square and "
            "identity_only for the other synthetic cases."
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
    parser.add_argument("--measure-memory", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cases = _selected_cases(args.case)
    rows = [
        run_qualification_case(
            case,
            k_max=k_max,
            cond_max=args.cond_max,
            eps_principal_max=args.eps_principal_max,
            N_at_max=args.N_at_max,
            w_match=args.w_match,
            n_atoms_A=args.n_atoms_A,
            n_atoms_B=args.n_atoms_B,
            surface_symmetry_mode=args.surface_symmetry_mode,
            pair_symmetry_policy=args.pair_symmetry_policy,
            correspondence_orientation=args.correspondence_orientation,
            identify_material_exchange=args.identify_material_exchange,
            correspondence_entry_limit=args.correspondence_entry_limit,
            measure_memory=args.measure_memory,
        )
        for k_max in args.k_max
        for case in cases
    ]
    write_qualification_csv(rows, args.out)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
