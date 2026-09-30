"""Run C6 direct-kernel/project/reopen public-API parity qualification."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from .claims.public_api_parity import (
    DEFAULT_FLOAT_ATOL,
    DEFAULT_FLOAT_RTOL,
    DEFAULT_PROFILE,
    SUPPORTED_PROFILES,
    PublicApiParityConfig,
    run_public_api_parity_qualification,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compare direct production-kernel, Project search, completed-search "
            "resume, and reopened-project candidate inventories."
        )
    )
    parser.add_argument(
        "--outdir",
        default="bench_out/claims_v1/C6_public_api_parity",
    )
    parser.add_argument(
        "--profile",
        choices=SUPPORTED_PROFILES,
        default=DEFAULT_PROFILE,
    )
    parser.add_argument(
        "--fixture",
        action="append",
        default=[],
        help="fixture identifier; repeat to select several",
    )
    parser.add_argument("--structure-lif", default=None)
    parser.add_argument("--structure-li2o", default=None)
    parser.add_argument("--layers", type=int, default=4)
    parser.add_argument("--vacuum", type=float, default=15.0)
    parser.add_argument("--float-atol", type=float, default=DEFAULT_FLOAT_ATOL)
    parser.add_argument("--float-rtol", type=float, default=DEFAULT_FLOAT_RTOL)
    parser.add_argument(
        "--no-reset-project",
        action="store_true",
        help="refuse to remove an existing qualification project",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    command_tail = list(argv) if argv is not None else sys.argv[1:]
    command = (
        sys.executable,
        "-m",
        "benchmarks.run_public_api_parity_qualification",
        *command_tail,
    )
    artifacts = run_public_api_parity_qualification(
        output_root=args.outdir,
        repository_root=REPOSITORY_ROOT,
        command=command,
        config=PublicApiParityConfig(
            profile=args.profile,
            fixture_ids=tuple(args.fixture),
            structure_lif=args.structure_lif,
            structure_li2o=args.structure_li2o,
            layers=args.layers,
            vacuum=args.vacuum,
            float_atol=args.float_atol,
            float_rtol=args.float_rtol,
            reset_project=not args.no_reset_project,
        ),
    )
    print(f"C6 status: {artifacts.result.status.value}")
    print(f"Manifest: {artifacts.manifest}")
    print(f"Claim result: {artifacts.claim_result}")
    print(f"Summary: {artifacts.summary}")
    print(f"Project database: {artifacts.project_database}")
    return 1 if artifacts.result.status.value == "fail" else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
