"""Qualify CALM's strain domain on a common gate-comparison population."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from .claims.gate_domain import (
    DEFAULT_CHECKPOINTS,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_HISTOGRAM_BIN_COUNT,
    DEFAULT_HISTOGRAM_MAX_STRAIN,
    DEFAULT_HISTOGRAM_MIN_STRAIN,
    DEFAULT_SAMPLE_COUNT,
    DEFAULT_SEED,
    GateDomainConfig,
    parse_checkpoints,
    run_gate_domain_qualification,
)
from .claims.manifest import repository_state


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _checkpoints_argument(value: str) -> tuple[int, ...]:
    try:
        return parse_checkpoints(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate CALM principal-strain admission and reduced-parameter "
            "gates on one seeded common candidate population."
        )
    )
    parser.add_argument(
        "--outdir",
        default="bench_out/claims_v1/C1_gate_domain",
    )
    parser.add_argument("--samples", type=int, default=DEFAULT_SAMPLE_COUNT)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    parser.add_argument(
        "--checkpoints",
        type=_checkpoints_argument,
        default=DEFAULT_CHECKPOINTS,
        help="comma-separated prefix sample counts",
    )
    parser.add_argument("--retain-samples", type=int, default=1_000)
    parser.add_argument("--examples-per-category", type=int, default=10)
    parser.add_argument("--max-principal-strain", type=float, default=0.03)
    parser.add_argument("--max-length-perturbation", type=float, default=0.03)
    parser.add_argument("--max-angle-perturbation-deg", type=float, default=1.5)
    parser.add_argument("--pymatgen-max-length-tol", type=float, default=0.03)
    parser.add_argument("--pymatgen-max-angle-tol", type=float, default=0.01)
    parser.add_argument(
        "--histogram-bins",
        type=int,
        default=DEFAULT_HISTOGRAM_BIN_COUNT,
    )
    parser.add_argument(
        "--histogram-min-strain",
        type=float,
        default=DEFAULT_HISTOGRAM_MIN_STRAIN,
    )
    parser.add_argument(
        "--histogram-max-strain",
        type=float,
        default=DEFAULT_HISTOGRAM_MAX_STRAIN,
    )
    parser.add_argument(
        "--require-clean-repository",
        action="store_true",
        help=(
            "refuse to run unless the CALM repository has a committed HEAD "
            "and a clean worktree"
        ),
    )
    return parser


def config_from_args(args: argparse.Namespace) -> GateDomainConfig:
    return GateDomainConfig(
        sample_count=args.samples,
        seed=args.seed,
        chunk_size=args.chunk_size,
        checkpoints=tuple(args.checkpoints),
        retained_sample_count=args.retain_samples,
        disagreement_examples_per_category=args.examples_per_category,
        maximum_length_perturbation=args.max_length_perturbation,
        maximum_angle_perturbation_deg=args.max_angle_perturbation_deg,
        max_principal_strain=args.max_principal_strain,
        pymatgen_max_length_tol=args.pymatgen_max_length_tol,
        pymatgen_max_angle_tol=args.pymatgen_max_angle_tol,
        histogram_bin_count=args.histogram_bins,
        histogram_min_strain=args.histogram_min_strain,
        histogram_max_strain=args.histogram_max_strain,
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.require_clean_repository:
        state = repository_state(REPOSITORY_ROOT)
        if state.commit is None or state.dirty is not False:
            detail = "unknown" if state.dirty is None else str(state.dirty).lower()
            raise RuntimeError(
                "Publication qualification requires a committed clean CALM "
                f"repository; commit={state.commit!r}, dirty={detail}."
            )
    command_tail = list(argv) if argv is not None else sys.argv[1:]
    command = (
        sys.executable,
        "-m",
        "benchmarks.run_gate_domain_qualification",
        *command_tail,
    )
    artifacts = run_gate_domain_qualification(
        output_root=args.outdir,
        repository_root=REPOSITORY_ROOT,
        command=command,
        config=config_from_args(args),
    )
    print(f"C1 status: {artifacts.result.status.value}")
    print(f"Manifest: {artifacts.manifest}")
    print(f"Claim result: {artifacts.claim_result}")
    print(f"Gate summary: {artifacts.summary}")
    return 0 if artifacts.result.status.value == "pass" else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
