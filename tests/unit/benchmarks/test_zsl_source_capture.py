from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest

from benchmarks.benchmarks.benchmark_pairs import LatticePair2D
from benchmarks.benchmarks.claims.matrix_conventions import (
    reconstruct_integer_transform_from_row_vectors,
)
from benchmarks.benchmarks.claims.zsl.raw_adapter import capture_raw_zsl_match
from benchmarks.benchmarks.claims.zsl.source_capture import capture_zsl_sources
from benchmarks.benchmarks.claims.zsl.transformation_reconstruction import (
    reconstruct_zsl_source_pair,
)


@dataclass
class FakeZSLMatch:
    film_sl_vectors: np.ndarray
    substrate_sl_vectors: np.ndarray
    film_vectors: np.ndarray
    substrate_vectors: np.ndarray
    film_transformation: np.ndarray
    substrate_transformation: np.ndarray
    match_transformation: np.ndarray

    @property
    def match_area(self) -> float:
        return float(np.linalg.norm(np.cross(*self.film_sl_vectors)))

    def as_dict(self) -> dict[str, object]:
        return {
            "@module": "pymatgen.analysis.interfaces.zsl",
            "@class": "ZSLMatch",
            "film_transformation": self.film_transformation,
            "custom_numpy_scalar": np.float64(2.5),
        }


def _match(*, perturb_film: float = 0.0) -> FakeZSLMatch:
    film_vectors = np.array(
        [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
        ]
    )
    substrate_vectors = np.array(
        [
            [2.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
        ]
    )
    film_row_left = np.array([[2, 1], [-1, 2]], dtype=int)
    substrate_row_left = np.array([[1, 1], [0, 2]], dtype=int)
    film_sl = film_row_left @ film_vectors
    film_sl[0, 0] += perturb_film
    substrate_sl = substrate_row_left @ substrate_vectors
    return FakeZSLMatch(
        film_sl_vectors=film_sl,
        substrate_sl_vectors=substrate_sl,
        film_vectors=film_vectors,
        substrate_vectors=substrate_vectors,
        film_transformation=film_row_left,
        substrate_transformation=substrate_row_left,
        match_transformation=np.eye(3),
    )


def _raw(match: FakeZSLMatch):
    return capture_raw_zsl_match(
        match,
        tool_version="test-version",
        fixture_id="test_pair",
        run_id="max_area_10",
        raw_index=0,
        generator_settings={
            "max_area": 10.0,
            "max_length_tol": 0.03,
            "max_angle_tol": 0.01,
            "max_area_ratio_tol": 0.09,
            "bidirectional": False,
        },
        invocation={"input_kind": "two_3d_row_vectors"},
    )


def test_embedded_row_vector_reconstruction_returns_column_right_map() -> None:
    primitive = np.array(
        [
            [1.0, 0.0, 1.0],
            [0.0, 2.0, 1.0],
        ]
    )
    row_left = np.array([[2, 1], [-1, 2]], dtype=int)
    superlattice = row_left @ primitive

    result = reconstruct_integer_transform_from_row_vectors(
        primitive,
        superlattice,
    )

    assert result.success is True
    assert result.integer_matrix == ((2, -1), (1, 2))
    assert result.determinant == 5
    assert result.source_index == 5


def test_raw_zsl_capture_preserves_scientific_fields_and_mson_payload() -> None:
    raw = _raw(_match())
    payload = raw.to_dict()["payload"]

    assert payload["source_match_id"] == (
        "pymatgen_zsl:test_pair:max_area_10:0"
    )
    assert set(payload["fields"]) >= {
        "film_sl_vectors",
        "substrate_sl_vectors",
        "film_vectors",
        "substrate_vectors",
        "film_transformation",
        "substrate_transformation",
        "match_transformation",
        "match_area",
    }
    assert payload["fields"]["film_transformation"] == [[2, 1], [-1, 2]]
    assert payload["mson_payload"]["@class"] == "ZSLMatch"
    assert payload["mson_payload"]["custom_numpy_scalar"] == 2.5
    json.dumps(raw.to_dict(), allow_nan=False)


def test_zsl_source_reconstruction_checks_both_sides_and_declared_indices() -> None:
    projected = reconstruct_zsl_source_pair(_raw(_match()))

    assert projected.status == "reconstructed"
    assert projected.identity["film_integer_matrix"] == [[2, -1], [1, 2]]
    assert projected.identity["film_source_index"] == 5
    assert projected.identity["substrate_integer_matrix"] == [[1, 0], [1, 2]]
    assert projected.identity["substrate_source_index"] == 2
    assert projected.diagnostics["failure_reasons"] == []
    assert (
        projected.diagnostics["declared_film_transformation"]
        ["source_index_matches_reconstruction"]
        is True
    )
    assert (
        projected.diagnostics["declared_substrate_transformation"]
        ["source_index_matches_reconstruction"]
        is True
    )


def test_failed_reconstruction_is_retained_with_nearest_integer_diagnostics() -> None:
    raw = _raw(_match(perturb_film=0.2))
    projected = reconstruct_zsl_source_pair(raw, atol=1.0e-12, rtol=1.0e-12)

    assert projected.source_match_id == raw.payload["source_match_id"]
    assert projected.status == "failed"
    assert projected.identity["film_integer_matrix"] == [[2, -1], [1, 2]]
    assert projected.diagnostics["film_reconstruction"]["success"] is False
    assert projected.diagnostics["film_reconstruction"][
        "maximum_absolute_residual"
    ] == pytest.approx(0.2)
    assert projected.diagnostics["failure_reasons"] == [
        "film: nearest integer transform failed residual check"
    ]


class FakeGenerator:
    def __init__(self, **settings: object) -> None:
        self.settings = settings

    def __call__(self, film_vectors, substrate_vectors):
        del film_vectors, substrate_vectors
        return [_match(), _match(perturb_film=0.2)]


def test_source_capture_writes_raw_and_failed_records_without_dropping_matches(
    tmp_path: Path,
) -> None:
    pair = LatticePair2D(
        name="synthetic",
        A=np.eye(2),
        B=np.diag([2.0, 1.0]),
        comment="Synthetic source-capture fixture.",
    )
    outdir = tmp_path / "source_capture"

    artifacts = capture_zsl_sources(
        output_root=outdir,
        repository_root=Path(__file__).resolve().parents[3],
        command=("python", "-m", "benchmarks.run_zsl_source_capture"),
        pairs=(pair,),
        max_areas=(10.0,),
        reconstruction_atol=1.0e-12,
        reconstruction_rtol=1.0e-12,
        generator_factory=FakeGenerator,
        tool_version="test-version",
    )

    raw_lines = artifacts.raw_matches.read_text(encoding="utf-8").splitlines()
    reconstruction_lines = artifacts.reconstructions.read_text(
        encoding="utf-8"
    ).splitlines()
    assert len(raw_lines) == 2
    assert len(reconstruction_lines) == 2

    raw_records = [json.loads(line) for line in raw_lines]
    projected_records = [json.loads(line) for line in reconstruction_lines]
    assert [record["raw_index"] for record in raw_records] == [0, 1]
    assert [record["status"] for record in projected_records] == [
        "reconstructed",
        "failed",
    ]

    summary = json.loads(artifacts.summary.read_text(encoding="utf-8"))
    assert summary["schema"] == "calm.zsl_source_capture_summary/v1"
    assert summary["scientific_claim_evaluated"] is False
    assert summary["raw_match_count"] == 2
    assert summary["reconstructed_count"] == 1
    assert summary["failed_count"] == 1
    assert summary["all_matches_retained"] is True

    manifest = json.loads(artifacts.manifest.read_text(encoding="utf-8"))
    assert manifest["selected_claims"] == ["C7"]
    assert manifest["policy_settings"]["stage"] == "zsl_source_capture"
    assert {artifact["path"] for artifact in manifest["artifacts"]} == {
        "raw_zsl_matches.jsonl",
        "zsl_source_reconstruction.jsonl",
        "source_capture_summary.json",
    }
