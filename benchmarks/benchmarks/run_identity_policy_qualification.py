"""Run C3/C4 coupled-identity policy and metamorphic qualification."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from .claims.claim_ids import ClaimId
from .claims.identity_policy import (
    DEFAULT_PROFILE,
    SUPPORTED_PROFILES,
    IdentityPolicyConfig,
    run_identity_policy_qualification,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate hand-declared coupled-identity distinctions, policy "
            "boundaries, and representation metamorphisms for claims C3 and C4."
        )
    )
    parser.add_argument(
        "--outdir",
        default="bench_out/claims_v1/C3_C4_identity_policy",
    )
    parser.add_argument(
        "--profile",
        choices=SUPPORTED_PROFILES,
        default=DEFAULT_PROFILE,
    )
    parser.add_argument(
        "--claim",
        action="append",
        choices=("C3", "C4"),
        help="claim to evaluate; repeat as needed (default: C3 and C4)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    selected = (
        tuple(ClaimId(value) for value in args.claim)
        if args.claim
        else (
            ClaimId.C3_COUPLED_IDENTITY,
            ClaimId.C4_REPRESENTATION_INVARIANCE,
        )
    )
    command_tail = list(argv) if argv is not None else sys.argv[1:]
    command = (
        sys.executable,
        "-m",
        "benchmarks.run_identity_policy_qualification",
        *command_tail,
    )
    artifacts = run_identity_policy_qualification(
        output_root=args.outdir,
        repository_root=REPOSITORY_ROOT,
        command=command,
        config=IdentityPolicyConfig(profile=args.profile),
        selected_claims=selected,
    )
    for result in artifacts.results:
        print(f"{result.claim_id.value} status: {result.status.value}")
    print(f"Manifest: {artifacts.manifest}")
    print(f"Summary: {artifacts.summary}")
    return 1 if any(result.status.value == "fail" for result in artifacts.results) else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
