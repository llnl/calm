"""Project retained pymatgen ZSL sources onto two declared identities."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from .claims.zsl.projection_suite import (
    load_point_group_file,
    project_captured_zsl_sources,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Project retained ZSL matches onto independent one-sided metric "
            "signatures and CALM primitive coupled-pair identity."
        )
    )
    parser.add_argument(
        "--capture-dir",
        required=True,
        help=(
            "Directory produced by benchmarks.run_zsl_source_capture and "
            "containing raw_zsl_matches.jsonl plus "
            "zsl_source_reconstruction.jsonl."
        ),
    )
    parser.add_argument(
        "--outdir",
        default="bench_out/claims_v1/C7_zsl_comparison/projection",
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
    parser.add_argument("--pair-key-version", type=int, default=1)
    parser.add_argument("--metric-signature-tolerance", type=float, default=1.0e-12)
    parser.add_argument("--metric-signature-scale", type=float, default=1.0e10)
    parser.add_argument("--surface-metric-tolerance", type=float, default=1.0e-8)
    parser.add_argument(
        "--point-groups",
        help=(
            "Optional JSON file using schema "
            "calm.zsl_projection_point_groups/v1. Unlisted fixtures use "
            "identity-only surface groups."
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.pair_key_version <= 0:
        raise SystemExit("--pair-key-version must be positive")
    if args.metric_signature_tolerance < 0:
        raise SystemExit("--metric-signature-tolerance must be nonnegative")
    if args.metric_signature_scale <= 0:
        raise SystemExit("--metric-signature-scale must be positive")
    if args.surface_metric_tolerance <= 0:
        raise SystemExit("--surface-metric-tolerance must be positive")

    command_tail = list(argv) if argv is not None else sys.argv[1:]
    command = (
        sys.executable,
        "-m",
        "benchmarks.run_zsl_projection",
        *command_tail,
    )
    artifacts = project_captured_zsl_sources(
        capture_root=args.capture_dir,
        output_root=args.outdir,
        repository_root=REPOSITORY_ROOT,
        command=command,
        pair_symmetry_policy=args.pair_symmetry_policy,
        correspondence_orientation=args.correspondence_orientation,
        identify_material_exchange=args.identify_material_exchange,
        pair_key_version=args.pair_key_version,
        metric_signature_tolerance=args.metric_signature_tolerance,
        metric_signature_scale=args.metric_signature_scale,
        surface_metric_tolerance=args.surface_metric_tolerance,
        point_groups_by_fixture=load_point_group_file(args.point_groups),
    )
    print("Projected retained ZSL evidence; claim C7 was not evaluated.")
    print(f"Manifest: {artifacts.manifest}")
    print(f"Metric projections: {artifacts.metric_projections}")
    print(f"Coupled projections: {artifacts.coupled_projections}")
    print(f"Summary: {artifacts.summary}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
