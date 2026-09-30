from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import numpy as np
import pytest

from benchmarks.benchmarks import run_gate_domain_qualification as runner_module
from benchmarks.benchmarks.claims.claim_ids import ClaimStatus
from benchmarks.benchmarks.claims import gate_domain as gate_domain_module
from benchmarks.benchmarks.claims.gate_domain import (
    CALM_GATE_ID,
    PYMATGEN_NATIVE_BIDIRECTIONAL_GATE_ID,
    PYMATGEN_NATIVE_UNIDIRECTIONAL_GATE_ID,
    TARGET_POPULATION_ID,
    GateDomainConfig,
    evaluate_boundary_suite,
    evaluate_trial_population,
    histogram_population_filename,
    histogram_population_ids,
    manuscript_gate_id,
    pymatgen_native_gate_batch,
    reduce_vectors_batch,
    run_gate_domain_qualification,
)
from benchmarks.benchmarks.common_metrics import airm_distance_and_strains
from benchmarks.benchmarks.claims.schemas import RepositoryState
from benchmarks.benchmarks.plot_gate_domain_evidence import (
    acceptance_summary_rows,
    load_gate_domain_histogram_evidence,
    render_gate_domain_evidence,
)


def _scalar_reduce(vector_set: np.ndarray) -> np.ndarray:
    first = np.asarray(vector_set[0], dtype=float)
    second = np.asarray(vector_set[1], dtype=float)
    if np.dot(first, second) < 0:
        return _scalar_reduce(np.stack((first, -second)))
    if np.linalg.norm(first) > np.linalg.norm(second):
        return _scalar_reduce(np.stack((second, first)))
    if np.linalg.norm(second) > np.linalg.norm(second + first):
        return _scalar_reduce(np.stack((first, second + first)))
    if np.linalg.norm(second) > np.linalg.norm(second - first):
        return _scalar_reduce(np.stack((first, second - first)))
    return np.stack((first, second))


def _angle(vector_set: np.ndarray) -> float:
    first, second = vector_set
    cross = first[0] * second[1] - first[1] * second[0]
    return math.atan2(abs(float(cross)), float(np.dot(first, second)))


def _scalar_native_gate(
    reference: np.ndarray,
    trial: np.ndarray,
    *,
    max_length_tol: float,
    max_angle_tol: float,
    bidirectional: bool,
) -> bool:
    ref = _scalar_reduce(reference)
    candidate = _scalar_reduce(trial)

    def one_way(first: np.ndarray, second: np.ndarray) -> bool:
        return (
            abs(np.linalg.norm(second[0]) / np.linalg.norm(first[0]) - 1.0)
            <= max_length_tol
            and abs(np.linalg.norm(second[1]) / np.linalg.norm(first[1]) - 1.0)
            <= max_length_tol
            and abs(_angle(second) / _angle(first) - 1.0) <= max_angle_tol
        )

    return one_way(ref, candidate) or (bidirectional and one_way(candidate, ref))


def test_boundary_suite_qualifies_exact_calm_strain_domain() -> None:
    config = GateDomainConfig(sample_count=100, checkpoints=(100,))
    candidates, decisions, summary = evaluate_boundary_suite(config)

    assert summary["passed"] is True
    assert summary["failure_count"] == 0
    assert summary["candidate_count"] == 108
    assert summary["maximum_principal_strain_error"] < 1.0e-12
    calm_decisions = [
        decision for decision in decisions if decision.gate_id == CALM_GATE_ID
    ]
    assert len(calm_decisions) == len(candidates)
    assert any(decision.admitted for decision in calm_decisions)
    assert any(not decision.admitted for decision in calm_decisions)
    for candidate, decision in zip(candidates, calm_decisions, strict=True):
        assert decision.admitted is candidate.parameters["expected_calm_admitted"]


def test_vectorized_pymatgen_replica_matches_scalar_source_contract() -> None:
    rng = np.random.default_rng(11)
    reference = np.array(
        [[3.1, 0.0], [2.3 * np.cos(np.radians(70.0)), 2.3 * np.sin(np.radians(70.0))]]
    )
    trials = []
    for values in rng.uniform(size=(200, 3)):
        delta_a = -0.03 + 0.06 * values[0]
        delta_b = -0.03 + 0.06 * values[1]
        delta_gamma = -1.5 + 3.0 * values[2]
        a = 3.1 * (1.0 + delta_a)
        b = 2.3 * (1.0 + delta_b)
        gamma = np.radians(70.0 + delta_gamma)
        trials.append(np.array([[a, 0.0], [b * np.cos(gamma), b * np.sin(gamma)]]))
    trial_array = np.asarray(trials)

    reduced = reduce_vectors_batch(trial_array)
    for index, trial in enumerate(trial_array):
        assert reduced[index] == pytest.approx(_scalar_reduce(trial))

    for bidirectional in (False, True):
        vectorized = pymatgen_native_gate_batch(
            reference,
            trial_array,
            max_length_tol=0.03,
            max_angle_tol=0.01,
            bidirectional=bidirectional,
        )
        scalar = np.asarray(
            [
                _scalar_native_gate(
                    reference,
                    trial,
                    max_length_tol=0.03,
                    max_angle_tol=0.01,
                    bidirectional=bidirectional,
                )
                for trial in trial_array
            ]
        )
        assert np.array_equal(vectorized, scalar)


def test_batched_principal_strains_match_scalar_metric_implementation() -> None:
    config = GateDomainConfig(sample_count=100, checkpoints=(100,))
    rng = np.random.default_rng(23)
    unit = rng.random((100, 3))
    delta_a = -0.03 + 0.06 * unit[:, 0]
    delta_b = -0.03 + 0.06 * unit[:, 1]
    delta_gamma = -1.5 + 3.0 * unit[:, 2]
    trial_rows = gate_domain_module._trial_rows_from_perturbations(
        delta_a,
        delta_b,
        delta_gamma,
        config,
    )
    batched = gate_domain_module._principal_strains_for_trial_rows(
        trial_rows,
        config,
    )
    reference_basis = gate_domain_module._reference_rows(config).T
    gram_a = reference_basis.T @ reference_basis

    for index, rows in enumerate(trial_rows):
        _, _, _, scalar = airm_distance_and_strains(
            gram_a,
            rows @ rows.T,
        )
        assert batched[index] == pytest.approx(scalar, abs=1.0e-13)


def test_trial_population_is_deterministic_across_chunk_sizes() -> None:
    common = dict(
        sample_count=5_000,
        seed=12345,
        checkpoints=(1_000, 5_000),
        retained_sample_count=25,
        disagreement_examples_per_category=3,
    )
    first = evaluate_trial_population(GateDomainConfig(chunk_size=127, **common))
    second = evaluate_trial_population(GateDomainConfig(chunk_size=2_048, **common))

    assert first["confusion_rows"] == second["confusion_rows"]
    assert first["convergence_rows"] == second["convergence_rows"]
    assert first["candidate_sample_rows"] == second["candidate_sample_rows"]
    assert first["disagreement_example_rows"] == second["disagreement_example_rows"]
    assert first["histogram_summary_rows"] == second["histogram_summary_rows"]
    assert np.array_equal(first["histogram_edges"], second["histogram_edges"])
    for population_id in histogram_population_ids(GateDomainConfig(**common)):
        assert np.array_equal(
            first["histogram_counts"][population_id],
            second["histogram_counts"][population_id],
        )

    by_gate = {row["gate_id"]: row for row in first["confusion_rows"]}
    assert by_gate[CALM_GATE_ID]["recall"] == pytest.approx(1.0)
    assert by_gate[CALM_GATE_ID]["false_positive_rate"] == pytest.approx(0.0)
    assert by_gate[manuscript_gate_id(1.5)]["accepted_fraction"] == pytest.approx(1.0)
    assert (
        by_gate[PYMATGEN_NATIVE_BIDIRECTIONAL_GATE_ID]["accepted_fraction"]
        >= by_gate[PYMATGEN_NATIVE_UNIDIRECTIONAL_GATE_ID]["accepted_fraction"]
    )


def test_gate_domain_runner_writes_versioned_c1_evidence(tmp_path: Path) -> None:
    output = tmp_path / "C1_gate_domain"
    config = GateDomainConfig(
        sample_count=5_000,
        seed=7,
        chunk_size=333,
        checkpoints=(1_000, 5_000),
        retained_sample_count=20,
        disagreement_examples_per_category=2,
    )
    artifacts = run_gate_domain_qualification(
        output_root=output,
        repository_root=Path(__file__).resolve().parents[3],
        command=("python-test", "gate-domain"),
        config=config,
    )

    assert artifacts.result.status is ClaimStatus.PASS
    assert artifacts.manifest.is_file()
    assert artifacts.claim_result.is_file()
    assert all(path.is_file() for path in artifacts.evidence_paths)

    summary = json.loads(artifacts.summary.read_text(encoding="utf-8"))
    assert summary["schema"] == "calm.gate_domain_summary/v1"
    assert summary["boundary_suite"]["passed"] is True
    assert summary["trial_population"]["sample_count"] == 5_000
    assert summary["interpretation"]["c7_status"] == "not_complete"
    histogram_payload = summary["trial_population"]["principal_strain_histograms"]
    assert histogram_payload["bin_edges_file"] == (
        "principal_strain_histogram_bin_edges.csv"
    )
    assert histogram_payload["summary_file"] == (
        "principal_strain_histogram_summary.csv"
    )
    assert set(histogram_payload["population_files"]) == {
        histogram_population_filename(config, population_id)
        for population_id in histogram_population_ids(config)
    }

    with artifacts.confusion_matrix.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert {row["gate_id"] for row in rows} >= {
        CALM_GATE_ID,
        manuscript_gate_id(0.5),
        manuscript_gate_id(1.0),
        manuscript_gate_id(1.5),
        PYMATGEN_NATIVE_UNIDIRECTIONAL_GATE_ID,
        PYMATGEN_NATIVE_BIDIRECTIONAL_GATE_ID,
    }


def test_histogram_artifacts_are_byte_deterministic_across_chunk_sizes(
    tmp_path: Path,
) -> None:
    common = dict(
        sample_count=8_000,
        seed=4242,
        checkpoints=(1_000, 8_000),
        retained_sample_count=10,
        disagreement_examples_per_category=2,
        histogram_bin_count=32,
    )
    outputs = []
    for name, chunk_size in (("small", 127), ("large", 2_048)):
        artifacts = run_gate_domain_qualification(
            output_root=tmp_path / name,
            repository_root=Path(__file__).resolve().parents[3],
            command=("python-test", name),
            config=GateDomainConfig(chunk_size=chunk_size, **common),
        )
        outputs.append(artifacts)

    first, second = outputs
    assert (
        first.histogram_bin_edges.read_bytes()
        == second.histogram_bin_edges.read_bytes()
    )
    assert first.histogram_summary.read_bytes() == second.histogram_summary.read_bytes()
    assert [path.name for path in first.histogram_files] == [
        path.name for path in second.histogram_files
    ]
    for first_path, second_path in zip(
        first.histogram_files,
        second.histogram_files,
        strict=True,
    ):
        assert first_path.read_bytes() == second_path.read_bytes()


def test_histogram_evidence_validates_confusion_counts_and_renders(
    tmp_path: Path,
) -> None:
    output = tmp_path / "benchmark"
    artifacts = run_gate_domain_qualification(
        output_root=output,
        repository_root=Path(__file__).resolve().parents[3],
        command=("python-test", "histogram-evidence"),
        config=GateDomainConfig(
            sample_count=6_000,
            seed=91,
            chunk_size=389,
            checkpoints=(1_000, 6_000),
            retained_sample_count=10,
            disagreement_examples_per_category=2,
            histogram_bin_count=30,
        ),
    )

    evidence = load_gate_domain_histogram_evidence(output)
    assert evidence.histograms[TARGET_POPULATION_ID].sum() == int(
        next(
            row["total_count"]
            for row in json.loads(artifacts.summary.read_text(encoding="utf-8"))[
                "trial_population"
            ]["principal_strain_histograms"]["populations"]
            if row["population_id"] == TARGET_POPULATION_ID
        )
    )
    rows = acceptance_summary_rows(evidence)
    assert len(rows) == 4
    assert rows[-1]["gate_id"] == CALM_GATE_ID
    assert rows[-1]["target_retained_fraction"] == pytest.approx(1.0)
    assert rows[-1]["outside_target_accepted_fraction"] == pytest.approx(0.0)

    pytest.importorskip("matplotlib")
    outputs = render_gate_domain_evidence(
        evidence,
        output_root=tmp_path / "plots",
        dpi=72,
    )
    assert all(path.is_file() for path in outputs.values())

    histogram_path = artifacts.histogram_files[0]
    original = histogram_path.read_bytes()
    histogram_path.write_bytes(original + b"\n")
    with pytest.raises(RuntimeError, match="Manifest checksum mismatch"):
        load_gate_domain_histogram_evidence(output)
    histogram_path.write_bytes(original)


def test_runner_rejects_histogram_bounds_that_clip_accepted_cells(
    tmp_path: Path,
) -> None:
    output = tmp_path / "clipped"
    with pytest.raises(
        RuntimeError,
        match="histogram bounds excluded accepted candidates",
    ):
        run_gate_domain_qualification(
            output_root=output,
            repository_root=Path(__file__).resolve().parents[3],
            command=("python-test", "clipped-histogram"),
            config=GateDomainConfig(
                sample_count=1_000,
                checkpoints=(1_000,),
                histogram_bin_count=20,
                histogram_min_strain=-0.005,
                histogram_max_strain=0.005,
            ),
        )
    assert not output.exists() or not any(output.iterdir())


def test_cli_can_require_a_clean_committed_repository(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        runner_module,
        "repository_state",
        lambda _root: RepositoryState(
            root="/tmp/calm",
            commit="abc123",
            dirty=True,
        ),
    )
    with pytest.raises(
        RuntimeError,
        match="requires a committed clean CALM repository",
    ):
        runner_module.main(
            (
                "--outdir",
                str(tmp_path / "output"),
                "--samples",
                "10",
                "--checkpoints",
                "10",
                "--require-clean-repository",
            )
        )
