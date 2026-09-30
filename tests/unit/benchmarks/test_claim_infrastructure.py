from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from benchmarks.benchmarks.claims.claim_ids import (
    CLAIM_REGISTRY,
    ClaimId,
    ClaimStatus,
    ordered_claim_ids,
    parse_claim_id,
)
from benchmarks.benchmarks.claims.fixtures import fixture_descriptor
from benchmarks.benchmarks.claims.manifest import sha256_file
from benchmarks.benchmarks.claims.matrix_conventions import (
    BASIS_VECTOR_STORAGE,
    SUPERCELL_CONVENTION,
    apply_integer_transform,
    column_basis_to_row_vectors,
    reconstruct_integer_transform,
    row_vectors_to_column_basis,
)
from benchmarks.benchmarks.claims.schemas import (
    BENCHMARK_MANIFEST_SCHEMA,
    CLAIM_RESULT_SCHEMA,
    CLAIM_SUMMARY_SCHEMA,
    GATE_CANDIDATE_SCHEMA,
    GATE_DECISION_SCHEMA,
    IDENTITY_POLICY_OBSERVATION_SCHEMA,
    METAMORPHIC_OBSERVATION_SCHEMA,
    PERFORMANCE_MEASUREMENT_SCHEMA,
    PUBLIC_API_PARITY_COMPARISON_SCHEMA,
    PUBLIC_API_PARITY_FIXTURE_SCHEMA,
    PUBLIC_API_PARITY_INVENTORY_SCHEMA,
    PROJECTED_MATCH_SCHEMA,
    RAW_EXTERNAL_MATCH_SCHEMA,
    REFERENCE_COMPARISON_SCHEMA,
    ZSL_ORACLE_COMPARISON_SCHEMA,
    ZSL_ORACLE_FIXTURE_SCHEMA,
    ZSL_ORACLE_KEY_OBSERVATION_SCHEMA,
    ZSL_ORACLE_SUMMARY_SCHEMA,
    ClaimResult,
    GateCandidate,
    GateDecision,
    IdentityPolicyObservation,
    MetamorphicObservation,
    PerformanceMeasurement,
    ProjectedMatch,
    RawExternalMatch,
    ReferenceComparison,
)
from benchmarks.benchmarks.run_claim_suite import main, run_claim_suite_scaffold


def test_claim_registry_has_stable_ordered_c1_through_c8() -> None:
    claim_ids = ordered_claim_ids()

    assert tuple(claim.value for claim in claim_ids) == (
        "C1",
        "C2",
        "C3",
        "C4",
        "C5",
        "C6",
        "C7",
        "C8",
    )
    assert set(CLAIM_REGISTRY) == set(claim_ids)
    assert parse_claim_id("c7") is ClaimId.C7_ZSL_COMPARISON
    with pytest.raises(ValueError, match="unknown claim identifier"):
        parse_claim_id("C9")


def test_claim_result_does_not_allow_scaffold_to_masquerade_as_evidence() -> None:
    placeholder = ClaimResult(
        claim_id=ClaimId.C2_FINITE_COMPLETENESS,
        status=ClaimStatus.NOT_RUN,
        summary="Reference differential stage is not implemented.",
    )
    assert placeholder.to_dict()["schema"] == CLAIM_RESULT_SCHEMA

    with pytest.raises(ValueError, match="must not cite scientific evidence"):
        ClaimResult(
            claim_id=ClaimId.C2_FINITE_COMPLETENESS,
            status=ClaimStatus.NOT_RUN,
            summary="Not run.",
            evidence_files=("reference-comparison.json",),
        )

    with pytest.raises(ValueError, match="must cite at least one evidence file"):
        ClaimResult(
            claim_id=ClaimId.C2_FINITE_COMPLETENESS,
            status=ClaimStatus.PASS,
            summary="Passed.",
        )


def test_evidence_record_schemas_are_versioned_and_json_serializable() -> None:
    digest = "0" * 64
    raw = RawExternalMatch(
        tool="pymatgen_zsl",
        tool_version="test",
        fixture_id="square",
        raw_index=0,
        payload={"film_transformation": [[1, 0], [0, 1]]},
    )
    projected = ProjectedMatch(
        source_match_id="zsl:0",
        projection_kind="metric_pair",
        status="projected",
        identity={"signature": "identity"},
    )
    candidate = GateCandidate(
        candidate_id="candidate:0",
        population="test",
        basis_A=((1.0, 0.0), (0.0, 1.0)),
        basis_B=((1.01, 0.0), (0.0, 1.0)),
        parameters={"expected": "inside"},
    )
    gate = GateDecision(
        candidate_id="candidate:0",
        gate_id="calm_principal_strain",
        admitted=True,
        measurements={"max_abs_principal_strain": 0.01},
        thresholds={"maximum": 0.03},
    )
    identity_observation = IdentityPolicyObservation(
        observation_id="C3.test",
        claim_id=ClaimId.C3_COUPLED_IDENTITY,
        category="test",
        expected_outcome="distinct",
        actual_outcome="distinct",
        passed=True,
        policy={"pair_symmetry_policy": "full"},
        baseline={"status": "projected"},
        variant={"status": "projected"},
    )
    metamorphic = MetamorphicObservation(
        observation_id="C4.test",
        transformation="common-right relabeling",
        expected_relation="equivalent",
        actual_relation="equivalent",
        passed=True,
        policy={"pair_symmetry_policy": "full"},
        baseline={"status": "projected"},
        transformed={"status": "projected"},
    )
    comparison = ReferenceComparison(
        fixture_id="square",
        domain={"k_max": 5},
        production_key_digest=digest,
        reference_key_digest=digest,
        production_count=2,
        reference_count=2,
    )
    timing = PerformanceMeasurement(
        implementation="production",
        fixture_id="square",
        repetition=0,
        elapsed_seconds=0.1,
        peak_rss_bytes=1024,
        output_digest=digest,
    )

    assert raw.to_dict()["schema"] == RAW_EXTERNAL_MATCH_SCHEMA
    assert projected.to_dict()["schema"] == PROJECTED_MATCH_SCHEMA
    assert candidate.to_dict()["schema"] == GATE_CANDIDATE_SCHEMA
    assert gate.to_dict()["schema"] == GATE_DECISION_SCHEMA
    assert (
        identity_observation.to_dict()["schema"]
        == IDENTITY_POLICY_OBSERVATION_SCHEMA
    )
    assert metamorphic.to_dict()["schema"] == METAMORPHIC_OBSERVATION_SCHEMA
    assert comparison.to_dict()["schema"] == REFERENCE_COMPARISON_SCHEMA
    assert comparison.exact_match is True
    assert timing.to_dict()["schema"] == PERFORMANCE_MEASUREMENT_SCHEMA
    assert PUBLIC_API_PARITY_FIXTURE_SCHEMA.endswith("/v1")
    assert PUBLIC_API_PARITY_INVENTORY_SCHEMA.endswith("/v1")
    assert PUBLIC_API_PARITY_COMPARISON_SCHEMA.endswith("/v1")
    assert ZSL_ORACLE_SUMMARY_SCHEMA == "calm.zsl_oracle_summary/v1"
    assert ZSL_ORACLE_FIXTURE_SCHEMA == "calm.zsl_oracle_fixture/v1"
    assert ZSL_ORACLE_COMPARISON_SCHEMA == "calm.zsl_oracle_comparison/v1"
    assert ZSL_ORACLE_KEY_OBSERVATION_SCHEMA.endswith("/v1")


def test_matrix_conventions_round_trip_and_reconstruct_integer_source() -> None:
    assert BASIS_VECTOR_STORAGE == "columns"
    assert SUPERCELL_CONVENTION == "S = A @ N"

    row_vectors = np.array([[2.0, 0.0], [0.5, 1.5]])
    basis = row_vectors_to_column_basis(row_vectors)
    assert np.array_equal(column_basis_to_row_vectors(basis), row_vectors)

    transform = np.array([[2, -1], [1, 2]], dtype=int)
    supercell = apply_integer_transform(basis, transform)
    reconstruction = reconstruct_integer_transform(basis, supercell)

    assert reconstruction.success is True
    assert reconstruction.integer_matrix == ((2, -1), (1, 2))
    assert reconstruction.determinant == 5
    assert reconstruction.source_index == 5
    assert reconstruction.orientation_sign == 1
    assert reconstruction.maximum_absolute_residual == pytest.approx(0.0)


def test_matrix_reconstruction_retains_failed_nearest_integer_diagnostics() -> None:
    basis = np.eye(2)
    supercell = np.array([[1.0, 0.2], [0.0, 1.0]])

    reconstruction = reconstruct_integer_transform(
        basis,
        supercell,
        atol=1.0e-12,
        rtol=1.0e-12,
    )

    assert reconstruction.success is False
    assert reconstruction.integer_matrix == ((1, 0), (0, 1))
    assert reconstruction.maximum_absolute_residual == pytest.approx(0.2)


def test_fixture_hash_is_deterministic_and_convention_bearing() -> None:
    fixture = fixture_descriptor(
        fixture_id="square_identity",
        family="equal_square",
        description="Infrastructure fixture for deterministic hashing.",
        basis_A=np.eye(2),
        basis_B=np.eye(2),
        claims=(ClaimId.C2_FINITE_COMPLETENESS,),
        tags=("exact",),
    )

    payload = fixture.to_dict()
    assert payload["basis_vector_storage"] == "columns"
    assert len(fixture.sha256()) == 64
    assert fixture.sha256() == fixture.sha256()


def test_claim_suite_scaffold_writes_manifest_and_not_run_results(
    tmp_path: Path,
) -> None:
    outdir = tmp_path / "scaffold"
    manifest_path, summary_path, markdown_path = run_claim_suite_scaffold(
        outdir=outdir,
        selected_claims=(ClaimId.C1_STRAIN_DOMAIN, ClaimId.C7_ZSL_COMPARISON),
        command=("python-test", "claim-scaffold"),
    )

    assert manifest_path.is_file()
    assert summary_path.is_file()
    assert markdown_path.is_file()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["scientific_qualification_executed"] is False
    assert {result["status"] for result in summary["results"]} == {"not_run"}


def test_claim_suite_executes_c1_and_keeps_c8_not_run(
    tmp_path: Path,
    capsys,
) -> None:
    outdir = tmp_path / "claims_v1"

    assert main(
        [
            "--outdir",
            str(outdir),
            "--claim",
            "C1",
            "--claim",
            "C8",
            "--gate-samples",
            "5000",
            "--gate-chunk-size",
            "333",
            "--gate-checkpoints",
            "1000,5000",
            "--gate-retain-samples",
            "20",
            "--gate-examples-per-category",
            "2",
        ]
    ) == 0

    output = capsys.readouterr().out
    assert "completed implemented stages" in output

    manifest_path = outdir / "benchmark_manifest.json"
    summary_path = outdir / "claim_summary.json"
    markdown_path = outdir / "claim_summary.md"
    assert manifest_path.is_file()
    assert summary_path.is_file()
    assert markdown_path.is_file()
    assert (outdir / "C1_gate_domain" / "gate_domain_summary.json").is_file()

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["schema"] == CLAIM_SUMMARY_SCHEMA
    assert summary["scientific_qualification_executed"] is True
    assert [result["claim_id"] for result in summary["results"]] == ["C1", "C8"]
    by_claim = {result["claim_id"]: result for result in summary["results"]}
    assert by_claim["C1"]["status"] == "pass"
    assert by_claim["C1"]["evidence_files"]
    assert all(
        path.startswith("C1_gate_domain/")
        for path in by_claim["C1"]["evidence_files"]
    )
    assert by_claim["C8"]["status"] == "not_run"
    assert not by_claim["C8"]["evidence_files"]

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema"] == BENCHMARK_MANIFEST_SCHEMA
    assert manifest["suite_version"] == "claims_v1"
    assert manifest["selected_claims"] == ["C1", "C8"]
    assert manifest["repository"]["commit"]
    artifacts = {artifact["path"]: artifact for artifact in manifest["artifacts"]}
    assert "claim_summary.json" in artifacts
    assert "claim_summary.md" in artifacts
    assert "C1_gate_domain/gate_domain_summary.json" in artifacts
    assert artifacts["claim_summary.json"]["sha256"] == sha256_file(summary_path)
    assert artifacts["claim_summary.md"]["sha256"] == sha256_file(markdown_path)


def test_claim_suite_executes_c2_reference_differential(
    tmp_path: Path,
    capsys,
) -> None:
    outdir = tmp_path / "claims_v1_c2"

    assert main(
        [
            "--outdir",
            str(outdir),
            "--claim",
            "C2",
            "--reference-profile",
            "smoke",
            "--reference-k-max",
            "2",
        ]
    ) == 0

    assert "completed implemented stages" in capsys.readouterr().out
    summary = json.loads(
        (outdir / "claim_summary.json").read_text(encoding="utf-8")
    )
    assert [result["claim_id"] for result in summary["results"]] == ["C2"]
    assert summary["results"][0]["status"] == "pass"
    assert all(
        path.startswith("C2_finite_completeness/")
        for path in summary["results"][0]["evidence_files"]
    )
    assert (
        outdir
        / "C2_finite_completeness"
        / "reference_differential_summary.json"
    ).is_file()


def test_claim_suite_executes_c3_and_c4_identity_qualification(
    tmp_path: Path,
    capsys,
) -> None:
    outdir = tmp_path / "claims_v1_identity"

    assert main(
        [
            "--outdir",
            str(outdir),
            "--claim",
            "C3",
            "--claim",
            "C4",
            "--identity-profile",
            "smoke",
        ]
    ) == 0

    assert "completed implemented stages" in capsys.readouterr().out
    summary = json.loads(
        (outdir / "claim_summary.json").read_text(encoding="utf-8")
    )
    assert [result["claim_id"] for result in summary["results"]] == ["C3", "C4"]
    assert {result["status"] for result in summary["results"]} == {"pass"}
    assert all(
        all(path.startswith("C3_C4_identity_policy/") for path in result["evidence_files"])
        for result in summary["results"]
    )
    assert (
        outdir
        / "C3_C4_identity_policy"
        / "identity_policy_summary.json"
    ).is_file()


def test_claim_suite_executes_c5_extension_stability(
    tmp_path: Path,
    capsys,
) -> None:
    outdir = tmp_path / "claims_v1_extension"

    assert main(
        [
            "--outdir",
            str(outdir),
            "--claim",
            "C5",
            "--extension-profile",
            "smoke",
            "--extension-fixture",
            "square_standard",
            "--extension-k-max",
            "2",
            "--extension-workers",
            "1",
        ]
    ) == 0

    assert "completed implemented stages" in capsys.readouterr().out
    summary = json.loads(
        (outdir / "claim_summary.json").read_text(encoding="utf-8")
    )
    assert [result["claim_id"] for result in summary["results"]] == ["C5"]
    assert summary["results"][0]["status"] == "pass"
    assert all(
        path.startswith("C5_extension_stability/")
        for path in summary["results"][0]["evidence_files"]
    )
    assert (
        outdir
        / "C5_extension_stability"
        / "search_extension_summary.json"
    ).is_file()


def test_claim_suite_executes_c7_controlled_zsl_comparison(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    from benchmarks.benchmarks.claims.zsl import oracle_comparison

    class IdentityGenerator:
        def __init__(self, **settings: object) -> None:
            self.settings = settings

        def __call__(self, film_vectors, substrate_vectors):
            identity = [[1, 0], [0, 1]]
            return [
                {
                    "film_sl_vectors": film_vectors,
                    "substrate_sl_vectors": substrate_vectors,
                    "film_vectors": film_vectors,
                    "substrate_vectors": substrate_vectors,
                    "film_transformation": identity,
                    "substrate_transformation": identity,
                    "match_transformation": np.eye(3).tolist(),
                    "match_area": 1.0,
                }
            ]

    monkeypatch.setattr(
        oracle_comparison,
        "default_generator_factory",
        IdentityGenerator,
    )
    monkeypatch.setattr(oracle_comparison, "pymatgen_version", lambda: "test-zsl")
    outdir = tmp_path / "claims_v1_c7"

    assert main(
        [
            "--outdir",
            str(outdir),
            "--claim",
            "C7",
            "--zsl-profile",
            "smoke",
            "--zsl-case",
            "equal_square_k5",
            "--zsl-k-max",
            "1",
            "--zsl-directionality",
            "unidirectional",
        ]
    ) == 0

    assert "completed implemented stages" in capsys.readouterr().out
    summary = json.loads(
        (outdir / "claim_summary.json").read_text(encoding="utf-8")
    )
    assert [result["claim_id"] for result in summary["results"]] == ["C7"]
    assert summary["results"][0]["status"] == "descriptive_only"
    assert all(
        path.startswith("C7_zsl_comparison/")
        for path in summary["results"][0]["evidence_files"]
    )
    assert (
        outdir / "C7_zsl_comparison" / "zsl_oracle_summary.json"
    ).is_file()
