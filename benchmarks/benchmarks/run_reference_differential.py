"""Run C2 production-versus-independent-reference differential qualification."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from .claims.differential_search import (
    DEFAULT_ATOM_LIMIT,
    DEFAULT_CONDITION_LIMIT,
    DEFAULT_EXACT_STRAIN_TOLERANCE,
    DEFAULT_PROFILE,
    ReferenceDifferentialConfig,
    run_reference_differential_qualification,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compare CALM's production coupled matcher with an independent "
            "exhaustive exact-rational reference on small finite domains."
        )
    )
    parser.add_argument(
        "--outdir",
        default="bench_out/claims_v1/C2_finite_completeness",
    )
    parser.add_argument(
        "--profile",
        choices=("smoke", "standard"),
        default=DEFAULT_PROFILE,
    )
    parser.add_argument(
        "--fixture",
        action="append",
        default=[],
        help="fixture identifier to run; repeat to select several",
    )
    parser.add_argument(
        "--k-max",
        type=int,
        default=None,
        help="override every selected fixture's recommended finite bound",
    )
    parser.add_argument(
        "--eps-principal-max",
        type=float,
        default=DEFAULT_EXACT_STRAIN_TOLERANCE,
    )
    parser.add_argument(
        "--cond-max",
        type=float,
        default=DEFAULT_CONDITION_LIMIT,
    )
    parser.add_argument(
        "--atom-limit",
        type=int,
        default=DEFAULT_ATOM_LIMIT,
    )
    return parser


def config_from_args(args: argparse.Namespace) -> ReferenceDifferentialConfig:
    return ReferenceDifferentialConfig(
        profile=args.profile,
        fixture_ids=tuple(args.fixture),
        k_max_override=args.k_max,
        eps_principal_max=args.eps_principal_max,
        cond_max=args.cond_max,
        atom_limit=args.atom_limit,
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    command_tail = list(argv) if argv is not None else sys.argv[1:]
    command = (
        sys.executable,
        "-m",
        "benchmarks.run_reference_differential",
        *command_tail,
    )
    artifacts = run_reference_differential_qualification(
        output_root=args.outdir,
        repository_root=REPOSITORY_ROOT,
        command=command,
        config=config_from_args(args),
    )
    print(f"C2 status: {artifacts.result.status.value}")
    print(f"Manifest: {artifacts.manifest}")
    print(f"Claim result: {artifacts.claim_result}")
    print(f"Differential summary: {artifacts.summary}")
    return 0 if artifacts.result.status.value == "pass" else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
