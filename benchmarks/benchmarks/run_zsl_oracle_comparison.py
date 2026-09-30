"""Run C7 controlled pymatgen ZSL comparison against finite CALM oracles."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from .claims.zsl.oracle_comparison import (
    DEFAULT_DIRECTIONALITY,
    DEFAULT_PROFILE,
    SUPPORTED_DIRECTIONALITIES,
    SUPPORTED_PROFILES,
    ZSLOracleComparisonConfig,
    run_zsl_oracle_comparison,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compare pymatgen ZSL output with exact finite CALM oracles after "
            "common source bounds, strain gates, and coupled-pair projection."
        )
    )
    parser.add_argument(
        "--outdir",
        default="bench_out/claims_v1/C7_zsl_comparison",
    )
    parser.add_argument(
        "--profile",
        choices=SUPPORTED_PROFILES,
        default=DEFAULT_PROFILE,
    )
    parser.add_argument(
        "--case",
        action="append",
        default=[],
        help="case identifier to run; repeat to select several",
    )
    parser.add_argument(
        "--k-max",
        type=int,
        default=None,
        help="override every selected case's finite source bound",
    )
    parser.add_argument(
        "--directionality",
        choices=SUPPORTED_DIRECTIONALITIES,
        default=DEFAULT_DIRECTIONALITY,
    )
    parser.add_argument("--max-area-ratio-tol", type=float, default=0.09)
    parser.add_argument("--max-length-tol", type=float, default=0.03)
    parser.add_argument("--max-angle-tol", type=float, default=0.01)
    parser.add_argument("--exact-strain-tolerance", type=float, default=1.0e-10)
    parser.add_argument("--common-strain-limit", type=float, default=0.03)
    parser.add_argument("--reconstruction-atol", type=float, default=1.0e-8)
    parser.add_argument("--reconstruction-rtol", type=float, default=1.0e-8)
    parser.add_argument("--cond-max", type=float, default=1.0e9)
    parser.add_argument("--atom-limit", type=int, default=100_000)
    return parser


def config_from_args(args: argparse.Namespace) -> ZSLOracleComparisonConfig:
    return ZSLOracleComparisonConfig(
        profile=args.profile,
        case_ids=tuple(args.case),
        k_max_override=args.k_max,
        directionality=args.directionality,
        max_area_ratio_tol=args.max_area_ratio_tol,
        max_length_tol=args.max_length_tol,
        max_angle_tol=args.max_angle_tol,
        exact_strain_tolerance=args.exact_strain_tolerance,
        common_strain_limit=args.common_strain_limit,
        reconstruction_atol=args.reconstruction_atol,
        reconstruction_rtol=args.reconstruction_rtol,
        cond_max=args.cond_max,
        atom_limit=args.atom_limit,
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    command_tail = list(argv) if argv is not None else sys.argv[1:]
    command = (
        sys.executable,
        "-m",
        "benchmarks.run_zsl_oracle_comparison",
        *command_tail,
    )
    artifacts = run_zsl_oracle_comparison(
        output_root=args.outdir,
        repository_root=REPOSITORY_ROOT,
        command=command,
        config=config_from_args(args),
    )
    print(f"C7 status: {artifacts.result.status.value}")
    print(f"Manifest: {artifacts.manifest}")
    print(f"Claim result: {artifacts.claim_result}")
    print(f"ZSL oracle summary: {artifacts.summary}")
    return 1 if artifacts.result.status.value == "fail" else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
