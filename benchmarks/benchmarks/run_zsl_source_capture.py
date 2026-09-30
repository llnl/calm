"""Capture raw pymatgen ZSL matches and reconstruct integer source maps.

This roadmap-PR3 command creates source evidence for claim C7. It does not yet
perform metric or coupled-identity projection and therefore does not declare the
CALM-versus-ZSL claim passed or failed.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from .benchmark_pairs import BENCHMARK_PAIRS, LatticePair2D
from .claims.zsl.source_capture import capture_zsl_sources


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Retain raw pymatgen ZSL matches and reconstruct their integer "
            "source transformations without evaluating claim C7."
        )
    )
    parser.add_argument(
        "--outdir",
        default="bench_out/claims_v1/C7_zsl_comparison/source_capture",
    )
    parser.add_argument(
        "--pair",
        action="append",
        choices=sorted(BENCHMARK_PAIRS),
        help="benchmark pair to capture; repeat as needed (default: all)",
    )
    parser.add_argument("--max-areas", default="50,100,200,400")
    parser.add_argument("--max-length-tol", type=_positive_float, default=0.03)
    parser.add_argument("--max-angle-tol", type=_positive_float, default=0.01)
    parser.add_argument("--max-area-ratio-tol", type=_positive_float, default=0.09)
    parser.add_argument("--bidirectional", action="store_true")
    parser.add_argument("--reconstruction-atol", type=float, default=1.0e-8)
    parser.add_argument("--reconstruction-rtol", type=float, default=1.0e-8)
    return parser


def _max_areas(value: str) -> tuple[float, ...]:
    try:
        areas = tuple(float(token.strip()) for token in value.split(",") if token.strip())
    except ValueError as exc:
        raise ValueError("--max-areas must be a comma-separated list of numbers") from exc
    if not areas or any(area <= 0 for area in areas):
        raise ValueError("--max-areas must contain positive values")
    return areas


def _pairs(names: Sequence[str] | None) -> tuple[LatticePair2D, ...]:
    selected = tuple(names or sorted(BENCHMARK_PAIRS))
    return tuple(BENCHMARK_PAIRS[name] for name in selected)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.reconstruction_atol < 0 or args.reconstruction_rtol < 0:
        raise SystemExit("reconstruction tolerances must be nonnegative")
    try:
        max_areas = _max_areas(args.max_areas)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    command_tail = list(argv) if argv is not None else sys.argv[1:]
    command = (
        sys.executable,
        "-m",
        "benchmarks.run_zsl_source_capture",
        *command_tail,
    )
    artifacts = capture_zsl_sources(
        output_root=args.outdir,
        repository_root=REPOSITORY_ROOT,
        command=command,
        pairs=_pairs(args.pair),
        max_areas=max_areas,
        max_area_ratio_tol=args.max_area_ratio_tol,
        max_length_tol=args.max_length_tol,
        max_angle_tol=args.max_angle_tol,
        bidirectional=args.bidirectional,
        reconstruction_atol=args.reconstruction_atol,
        reconstruction_rtol=args.reconstruction_rtol,
    )
    print("Captured raw pymatgen ZSL source evidence; claim C7 was not evaluated.")
    print(f"Manifest: {artifacts.manifest}")
    print(f"Raw matches: {artifacts.raw_matches}")
    print(f"Reconstructions: {artifacts.reconstructions}")
    print(f"Summary: {artifacts.summary}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
