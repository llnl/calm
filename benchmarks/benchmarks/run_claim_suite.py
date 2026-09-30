"""Run implemented claim qualifications and register remaining roadmap claims.

The claim suite is parallel to the frozen ``legacy_v1`` benchmark workflow.
Implemented claims execute their scientific stages; unimplemented claims remain
explicitly recorded as ``not_run`` without evidence attachments.

Usage
-----

.. code-block:: bash

    python -m benchmarks.run_claim_suite --outdir bench_out/claims_v1
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from .claims.claim_ids import (
    CLAIM_REGISTRY,
    ClaimId,
    ClaimStatus,
    ordered_claim_ids,
    parse_claim_id,
)
from .claims.gate_domain import (
    DEFAULT_CHECKPOINTS,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_SAMPLE_COUNT,
    DEFAULT_SEED,
    GateDomainConfig,
    parse_checkpoints,
    run_gate_domain_qualification,
)
from .claims.differential_search import (
    DEFAULT_ATOM_LIMIT as DEFAULT_REFERENCE_ATOM_LIMIT,
    DEFAULT_CONDITION_LIMIT as DEFAULT_REFERENCE_CONDITION_LIMIT,
    DEFAULT_EXACT_STRAIN_TOLERANCE,
    DEFAULT_PROFILE as DEFAULT_REFERENCE_PROFILE,
    ReferenceDifferentialConfig,
    run_reference_differential_qualification,
)
from .claims.identity_policy import (
    DEFAULT_PROFILE as DEFAULT_IDENTITY_PROFILE,
    SUPPORTED_PROFILES as IDENTITY_PROFILES,
    IdentityPolicyConfig,
    run_identity_policy_qualification,
)
from .claims.extension_stability import (
    DEFAULT_ATOM_LIMIT as DEFAULT_EXTENSION_ATOM_LIMIT,
    DEFAULT_CONDITION_LIMIT as DEFAULT_EXTENSION_CONDITION_LIMIT,
    DEFAULT_EXACT_STRAIN_TOLERANCE as DEFAULT_EXTENSION_STRAIN_TOLERANCE,
    DEFAULT_PROFILE as DEFAULT_EXTENSION_PROFILE,
    DEFAULT_WORKERS as DEFAULT_EXTENSION_WORKERS,
    SUPPORTED_PROFILES as EXTENSION_PROFILES,
    ExtensionStabilityConfig,
    run_extension_stability_qualification,
)
from .claims.public_api_parity import (
    DEFAULT_FLOAT_ATOL as DEFAULT_PUBLIC_API_FLOAT_ATOL,
    DEFAULT_FLOAT_RTOL as DEFAULT_PUBLIC_API_FLOAT_RTOL,
    DEFAULT_PROFILE as DEFAULT_PUBLIC_API_PROFILE,
    SUPPORTED_PROFILES as PUBLIC_API_PROFILES,
    PublicApiParityConfig,
    run_public_api_parity_qualification,
)
from .claims.zsl.oracle_comparison import (
    DEFAULT_DIRECTIONALITY as DEFAULT_ZSL_DIRECTIONALITY,
    DEFAULT_PROFILE as DEFAULT_ZSL_PROFILE,
    SUPPORTED_DIRECTIONALITIES as ZSL_DIRECTIONALITIES,
    SUPPORTED_PROFILES as ZSL_PROFILES,
    ZSLOracleComparisonConfig,
    run_zsl_oracle_comparison,
)
from .claims.manifest import artifact_record, build_manifest, write_json_atomic
from .claims.schemas import (
    CLAIM_SUITE_VERSION,
    CLAIM_SUMMARY_SCHEMA,
    ClaimResult,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _claim_argument(value: str) -> ClaimId:
    try:
        return parse_claim_id(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _checkpoints_argument(value: str) -> tuple[int, ...]:
    try:
        return parse_checkpoints(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run implemented claim-suite qualifications and record remaining "
            "claims as not_run."
        )
    )
    parser.add_argument("--outdir", default="bench_out/claims_v1")
    parser.add_argument(
        "--claim",
        action="append",
        type=_claim_argument,
        help="claim identifier to evaluate; repeat as needed (default: C1-C8)",
    )
    parser.add_argument("--gate-samples", type=int, default=DEFAULT_SAMPLE_COUNT)
    parser.add_argument("--gate-seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--gate-chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    parser.add_argument(
        "--gate-checkpoints",
        type=_checkpoints_argument,
        default=DEFAULT_CHECKPOINTS,
    )
    parser.add_argument("--gate-retain-samples", type=int, default=1_000)
    parser.add_argument("--gate-examples-per-category", type=int, default=10)
    parser.add_argument(
        "--reference-profile",
        choices=("smoke", "standard"),
        default=DEFAULT_REFERENCE_PROFILE,
    )
    parser.add_argument(
        "--reference-fixture",
        action="append",
        default=[],
        help="C2 fixture identifier; repeat to select several",
    )
    parser.add_argument("--reference-k-max", type=int, default=None)
    parser.add_argument(
        "--reference-eps-principal-max",
        type=float,
        default=DEFAULT_EXACT_STRAIN_TOLERANCE,
    )
    parser.add_argument(
        "--reference-cond-max",
        type=float,
        default=DEFAULT_REFERENCE_CONDITION_LIMIT,
    )
    parser.add_argument(
        "--reference-atom-limit",
        type=int,
        default=DEFAULT_REFERENCE_ATOM_LIMIT,
    )
    parser.add_argument(
        "--identity-profile",
        choices=IDENTITY_PROFILES,
        default=DEFAULT_IDENTITY_PROFILE,
    )
    parser.add_argument(
        "--extension-profile",
        choices=EXTENSION_PROFILES,
        default=DEFAULT_EXTENSION_PROFILE,
    )
    parser.add_argument(
        "--extension-fixture",
        action="append",
        default=[],
        help="C5 fixture identifier; repeat to select several",
    )
    parser.add_argument("--extension-k-max", type=int, default=None)
    parser.add_argument(
        "--extension-eps-principal-max",
        type=float,
        default=DEFAULT_EXTENSION_STRAIN_TOLERANCE,
    )
    parser.add_argument(
        "--extension-cond-max",
        type=float,
        default=DEFAULT_EXTENSION_CONDITION_LIMIT,
    )
    parser.add_argument(
        "--extension-atom-limit",
        type=int,
        default=DEFAULT_EXTENSION_ATOM_LIMIT,
    )
    parser.add_argument(
        "--extension-workers",
        type=int,
        default=DEFAULT_EXTENSION_WORKERS,
    )
    parser.add_argument(
        "--public-api-profile",
        choices=PUBLIC_API_PROFILES,
        default=DEFAULT_PUBLIC_API_PROFILE,
    )
    parser.add_argument(
        "--public-api-fixture",
        action="append",
        default=[],
        help="C6 fixture identifier; repeat to select several",
    )
    parser.add_argument("--public-api-structure-lif", default=None)
    parser.add_argument("--public-api-structure-li2o", default=None)
    parser.add_argument("--public-api-layers", type=int, default=4)
    parser.add_argument("--public-api-vacuum", type=float, default=15.0)
    parser.add_argument(
        "--public-api-float-atol",
        type=float,
        default=DEFAULT_PUBLIC_API_FLOAT_ATOL,
    )
    parser.add_argument(
        "--public-api-float-rtol",
        type=float,
        default=DEFAULT_PUBLIC_API_FLOAT_RTOL,
    )
    parser.add_argument(
        "--zsl-profile",
        choices=ZSL_PROFILES,
        default=DEFAULT_ZSL_PROFILE,
    )
    parser.add_argument(
        "--zsl-case",
        action="append",
        default=[],
        help="C7 oracle-comparison case identifier; repeat to select several",
    )
    parser.add_argument("--zsl-k-max", type=int, default=None)
    parser.add_argument(
        "--zsl-directionality",
        choices=ZSL_DIRECTIONALITIES,
        default=DEFAULT_ZSL_DIRECTIONALITY,
    )
    parser.add_argument("--zsl-max-area-ratio-tol", type=float, default=0.09)
    parser.add_argument("--zsl-max-length-tol", type=float, default=0.03)
    parser.add_argument("--zsl-max-angle-tol", type=float, default=0.01)
    parser.add_argument("--zsl-exact-strain-tolerance", type=float, default=1.0e-10)
    parser.add_argument("--zsl-common-strain-limit", type=float, default=0.03)
    parser.add_argument("--zsl-reconstruction-atol", type=float, default=1.0e-8)
    parser.add_argument("--zsl-reconstruction-rtol", type=float, default=1.0e-8)
    parser.add_argument("--zsl-cond-max", type=float, default=1.0e9)
    parser.add_argument("--zsl-atom-limit", type=int, default=100_000)
    return parser


def _selected_claims(values: Sequence[ClaimId] | None) -> tuple[ClaimId, ...]:
    if not values:
        return ordered_claim_ids()
    selected = set(values)
    return tuple(claim for claim in ordered_claim_ids() if claim in selected)


def _placeholder_result(claim_id: ClaimId) -> ClaimResult:
    definition = CLAIM_REGISTRY[claim_id]
    return ClaimResult(
        claim_id=claim_id,
        status=ClaimStatus.NOT_RUN,
        summary=(
            f"{definition.title} is registered, but its scientific qualification "
            "stage has not yet been implemented."
        ),
        notes=(
            "This record is a roadmap placeholder and is not scientific evidence.",
        ),
    )


def _prefix_evidence(result: ClaimResult, prefix: str) -> ClaimResult:
    return ClaimResult(
        claim_id=result.claim_id,
        status=result.status,
        summary=result.summary,
        evidence_files=tuple(f"{prefix}/{path}" for path in result.evidence_files),
        metrics=result.metrics,
        notes=result.notes,
        suite_version=result.suite_version,
    )


def _summary_payload(results: Sequence[ClaimResult]) -> dict[str, object]:
    executed = any(result.status is not ClaimStatus.NOT_RUN for result in results)
    return {
        "schema": CLAIM_SUMMARY_SCHEMA,
        "suite_version": CLAIM_SUITE_VERSION,
        "scientific_qualification_executed": executed,
        "results": [result.to_dict() for result in results],
    }


def _summary_markdown(results: Sequence[ClaimResult]) -> str:
    executed = any(result.status is not ClaimStatus.NOT_RUN for result in results)
    lines = [
        "# CALM claim-suite status",
        "",
        (
            "> Implemented scientific stages were executed; unimplemented "
            "claims remain explicitly `not_run`."
            if executed
            else "> No scientific qualification was executed."
        ),
        "",
        "| Claim | Status | Registered claim |",
        "|---|---|---|",
    ]
    for result in results:
        definition = CLAIM_REGISTRY[result.claim_id]
        lines.append(
            f"| `{result.claim_id.value}` | `{result.status.value}` | "
            f"{definition.statement} |"
        )
    lines.extend(
        [
            "",
            "The frozen historical benchmark suite remains under "
            "`benchmarks/legacy/` and is not modified by this command.",
            "",
        ]
    )
    return "\n".join(lines)


def _write_claim_summary(
    *,
    output_root: Path,
    results: Sequence[ClaimResult],
) -> tuple[Path, Path]:
    summary_json = write_json_atomic(
        output_root / "claim_summary.json",
        _summary_payload(results),
    )
    summary_markdown = output_root / "claim_summary.md"
    summary_markdown.write_text(
        _summary_markdown(results),
        encoding="utf-8",
    )
    return summary_json, summary_markdown


def run_claim_suite_scaffold(
    *,
    outdir: str | Path,
    selected_claims: Sequence[ClaimId],
    command: Sequence[str],
) -> tuple[Path, Path, Path]:
    """Retain the PR-2 no-science scaffold for tests and schema migration."""

    output_root = Path(outdir).expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    results = tuple(_placeholder_result(claim) for claim in selected_claims)
    summary_json, summary_markdown = _write_claim_summary(
        output_root=output_root,
        results=results,
    )
    artifacts = (
        artifact_record(
            summary_json,
            relative_to=output_root,
            media_type="application/json",
        ),
        artifact_record(
            summary_markdown,
            relative_to=output_root,
            media_type="text/markdown",
        ),
    )
    manifest = build_manifest(
        repository_root=REPOSITORY_ROOT,
        output_root=output_root,
        command=command,
        selected_claims=selected_claims,
        artifacts=artifacts,
    )
    manifest_path = write_json_atomic(
        output_root / "benchmark_manifest.json",
        manifest.to_dict(),
    )
    return manifest_path, summary_json, summary_markdown


def run_claim_suite(
    *,
    outdir: str | Path,
    selected_claims: Sequence[ClaimId],
    command: Sequence[str],
    gate_config: GateDomainConfig,
    reference_config: ReferenceDifferentialConfig,
    identity_config: IdentityPolicyConfig,
    extension_config: ExtensionStabilityConfig,
    public_api_config: PublicApiParityConfig,
    zsl_config: ZSLOracleComparisonConfig,
) -> tuple[Path, Path, Path, tuple[ClaimResult, ...]]:
    """Execute implemented claims and emit one aggregate status report."""

    output_root = Path(outdir).expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    results_by_claim: dict[ClaimId, ClaimResult] = {}
    stage_artifacts: list[Path] = []

    if ClaimId.C1_STRAIN_DOMAIN in selected_claims:
        stage_root = output_root / "C1_gate_domain"
        gate_artifacts = run_gate_domain_qualification(
            output_root=stage_root,
            repository_root=REPOSITORY_ROOT,
            command=command,
            config=gate_config,
        )
        results_by_claim[ClaimId.C1_STRAIN_DOMAIN] = _prefix_evidence(
            gate_artifacts.result,
            "C1_gate_domain",
        )
        stage_artifacts.extend(
            (
                gate_artifacts.manifest,
                gate_artifacts.claim_result,
                *gate_artifacts.evidence_paths,
            )
        )

    if ClaimId.C2_FINITE_COMPLETENESS in selected_claims:
        stage_root = output_root / "C2_finite_completeness"
        reference_artifacts = run_reference_differential_qualification(
            output_root=stage_root,
            repository_root=REPOSITORY_ROOT,
            command=command,
            config=reference_config,
        )
        results_by_claim[ClaimId.C2_FINITE_COMPLETENESS] = _prefix_evidence(
            reference_artifacts.result,
            "C2_finite_completeness",
        )
        stage_artifacts.extend(
            (
                reference_artifacts.manifest,
                reference_artifacts.claim_result,
                *reference_artifacts.evidence_paths,
            )
        )

    identity_claims = tuple(
        claim
        for claim in (
            ClaimId.C3_COUPLED_IDENTITY,
            ClaimId.C4_REPRESENTATION_INVARIANCE,
        )
        if claim in selected_claims
    )
    if identity_claims:
        stage_root = output_root / "C3_C4_identity_policy"
        identity_artifacts = run_identity_policy_qualification(
            output_root=stage_root,
            repository_root=REPOSITORY_ROOT,
            command=command,
            config=identity_config,
            selected_claims=identity_claims,
        )
        for result in identity_artifacts.results:
            results_by_claim[result.claim_id] = _prefix_evidence(
                result,
                "C3_C4_identity_policy",
            )
        stage_artifacts.extend(
            (
                identity_artifacts.manifest,
                *identity_artifacts.claim_result_paths,
                *identity_artifacts.evidence_paths,
            )
        )

    if ClaimId.C5_EXTENSION_STABILITY in selected_claims:
        stage_root = output_root / "C5_extension_stability"
        extension_artifacts = run_extension_stability_qualification(
            output_root=stage_root,
            repository_root=REPOSITORY_ROOT,
            command=command,
            config=extension_config,
        )
        results_by_claim[ClaimId.C5_EXTENSION_STABILITY] = _prefix_evidence(
            extension_artifacts.result,
            "C5_extension_stability",
        )
        stage_artifacts.extend(
            (
                extension_artifacts.manifest,
                extension_artifacts.claim_result,
                *extension_artifacts.evidence_paths,
            )
        )

    if ClaimId.C6_PUBLIC_API_PARITY in selected_claims:
        stage_root = output_root / "C6_public_api_parity"
        public_api_artifacts = run_public_api_parity_qualification(
            output_root=stage_root,
            repository_root=REPOSITORY_ROOT,
            command=command,
            config=public_api_config,
        )
        results_by_claim[ClaimId.C6_PUBLIC_API_PARITY] = _prefix_evidence(
            public_api_artifacts.result,
            "C6_public_api_parity",
        )
        stage_artifacts.extend(
            (
                public_api_artifacts.manifest,
                public_api_artifacts.claim_result,
                *public_api_artifacts.evidence_paths,
            )
        )

    if ClaimId.C7_ZSL_COMPARISON in selected_claims:
        stage_root = output_root / "C7_zsl_comparison"
        zsl_artifacts = run_zsl_oracle_comparison(
            output_root=stage_root,
            repository_root=REPOSITORY_ROOT,
            command=command,
            config=zsl_config,
        )
        results_by_claim[ClaimId.C7_ZSL_COMPARISON] = _prefix_evidence(
            zsl_artifacts.result,
            "C7_zsl_comparison",
        )
        stage_artifacts.extend(
            (
                zsl_artifacts.manifest,
                zsl_artifacts.claim_result,
                *zsl_artifacts.evidence_paths,
            )
        )

    results = tuple(
        results_by_claim.get(claim, _placeholder_result(claim))
        for claim in selected_claims
    )
    summary_json, summary_markdown = _write_claim_summary(
        output_root=output_root,
        results=results,
    )
    artifacts = [
        artifact_record(
            summary_json,
            relative_to=output_root,
            media_type="application/json",
        ),
        artifact_record(
            summary_markdown,
            relative_to=output_root,
            media_type="text/markdown",
        ),
    ]
    for path in stage_artifacts:
        media_type = "text/csv" if path.suffix == ".csv" else "application/json"
        artifacts.append(
            artifact_record(
                path,
                relative_to=output_root,
                media_type=media_type,
            )
        )
    manifest = build_manifest(
        repository_root=REPOSITORY_ROOT,
        output_root=output_root,
        command=command,
        selected_claims=selected_claims,
        artifacts=tuple(artifacts),
    )
    manifest_path = write_json_atomic(
        output_root / "benchmark_manifest.json",
        manifest.to_dict(),
    )
    return manifest_path, summary_json, summary_markdown, results


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    selected = _selected_claims(args.claim)
    command_tail = list(argv) if argv is not None else sys.argv[1:]
    command = (
        sys.executable,
        "-m",
        "benchmarks.run_claim_suite",
        *command_tail,
    )
    gate_config = GateDomainConfig(
        sample_count=args.gate_samples,
        seed=args.gate_seed,
        chunk_size=args.gate_chunk_size,
        checkpoints=tuple(args.gate_checkpoints),
        retained_sample_count=args.gate_retain_samples,
        disagreement_examples_per_category=args.gate_examples_per_category,
    )
    reference_config = ReferenceDifferentialConfig(
        profile=args.reference_profile,
        fixture_ids=tuple(args.reference_fixture),
        k_max_override=args.reference_k_max,
        eps_principal_max=args.reference_eps_principal_max,
        cond_max=args.reference_cond_max,
        atom_limit=args.reference_atom_limit,
    )
    identity_config = IdentityPolicyConfig(profile=args.identity_profile)
    extension_config = ExtensionStabilityConfig(
        profile=args.extension_profile,
        fixture_ids=tuple(args.extension_fixture),
        k_max_override=args.extension_k_max,
        eps_principal_max=args.extension_eps_principal_max,
        cond_max=args.extension_cond_max,
        atom_limit=args.extension_atom_limit,
        workers=args.extension_workers,
    )
    public_api_config = PublicApiParityConfig(
        profile=args.public_api_profile,
        fixture_ids=tuple(args.public_api_fixture),
        structure_lif=args.public_api_structure_lif,
        structure_li2o=args.public_api_structure_li2o,
        layers=args.public_api_layers,
        vacuum=args.public_api_vacuum,
        float_atol=args.public_api_float_atol,
        float_rtol=args.public_api_float_rtol,
        reset_project=True,
    )
    zsl_config = ZSLOracleComparisonConfig(
        profile=args.zsl_profile,
        case_ids=tuple(args.zsl_case),
        k_max_override=args.zsl_k_max,
        directionality=args.zsl_directionality,
        max_area_ratio_tol=args.zsl_max_area_ratio_tol,
        max_length_tol=args.zsl_max_length_tol,
        max_angle_tol=args.zsl_max_angle_tol,
        exact_strain_tolerance=args.zsl_exact_strain_tolerance,
        common_strain_limit=args.zsl_common_strain_limit,
        reconstruction_atol=args.zsl_reconstruction_atol,
        reconstruction_rtol=args.zsl_reconstruction_rtol,
        cond_max=args.zsl_cond_max,
        atom_limit=args.zsl_atom_limit,
    )
    manifest_path, summary_json, summary_markdown, results = run_claim_suite(
        outdir=args.outdir,
        selected_claims=selected,
        command=command,
        gate_config=gate_config,
        reference_config=reference_config,
        identity_config=identity_config,
        extension_config=extension_config,
        public_api_config=public_api_config,
        zsl_config=zsl_config,
    )
    executed = [
        result for result in results if result.status is not ClaimStatus.NOT_RUN
    ]
    if executed:
        print(
            "Claim suite completed implemented stages; remaining claims are "
            "recorded as not_run."
        )
    else:
        print("Claim-suite registry initialized; no scientific stages ran.")
    print(f"Manifest: {manifest_path}")
    print(f"JSON summary: {summary_json}")
    print(f"Markdown summary: {summary_markdown}")
    return 1 if any(result.status is ClaimStatus.FAIL for result in results) else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
