from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from calm.interface.matching._types import PairIdentityPolicy2D

from benchmarks.benchmarks.benchmark_pairs import LatticePair2D
from benchmarks.benchmarks.claims.zsl.coupled_projection import (
    project_zsl_coupled_pair,
)
from benchmarks.benchmarks.claims.zsl.metric_projection import (
    project_zsl_metric_pair,
)
from benchmarks.benchmarks.claims.zsl.projection_suite import (
    POINT_GROUP_FILE_SCHEMA,
    load_point_group_file,
    project_captured_zsl_sources,
)
from benchmarks.benchmarks.claims.zsl.raw_adapter import capture_raw_zsl_match
from benchmarks.benchmarks.claims.zsl.source_capture import capture_zsl_sources
from benchmarks.benchmarks.claims.zsl.transformation_reconstruction import (
    reconstruct_zsl_source_pair,
)
from benchmarks.benchmarks.qualification_fixtures import full_square_point_group


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


def _embedded_identity_rows() -> np.ndarray:
    return np.array(
        [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
        ]
    )


def _match_from_column_maps(
    source_a: np.ndarray,
    source_b: np.ndarray,
) -> FakeZSLMatch:
    primitive = _embedded_identity_rows()
    row_left_a = np.asarray(source_a, dtype=int).T
    row_left_b = np.asarray(source_b, dtype=int).T
    return FakeZSLMatch(
        film_sl_vectors=row_left_a @ primitive,
        substrate_sl_vectors=row_left_b @ primitive,
        film_vectors=primitive,
        substrate_vectors=primitive,
        film_transformation=row_left_a,
        substrate_transformation=row_left_b,
        match_transformation=np.eye(3),
    )


def _raw(match: FakeZSLMatch, *, raw_index: int = 0):
    return capture_raw_zsl_match(
        match,
        tool_version="test-version",
        fixture_id="equal_square",
        run_id="max_area_10",
        raw_index=raw_index,
        generator_settings={"max_area": 10.0, "bidirectional": False},
        invocation={"film_role": "A", "substrate_role": "B"},
    )


def _policy(*, orientation: str = "proper") -> PairIdentityPolicy2D:
    return PairIdentityPolicy2D(
        pair_symmetry="full",
        correspondence_orientation=orientation,  # type: ignore[arg-type]
        identify_material_exchange=False,
    )


def test_metric_projection_merges_equal_metrics_but_not_coupled_keys() -> None:
    identity = np.eye(2, dtype=int)
    c4 = np.array([[2, -1], [1, 2]], dtype=int)
    c5 = np.array([[1, -2], [2, 1]], dtype=int)
    raw_c4 = _raw(_match_from_column_maps(identity, c4), raw_index=0)
    raw_c5 = _raw(_match_from_column_maps(identity, c5), raw_index=1)

    metric_c4 = project_zsl_metric_pair(raw_c4)
    metric_c5 = project_zsl_metric_pair(raw_c5)
    coupled_c4 = project_zsl_coupled_pair(
        raw_c4,
        reconstruct_zsl_source_pair(raw_c4),
        policy=_policy(),
    )
    coupled_c5 = project_zsl_coupled_pair(
        raw_c5,
        reconstruct_zsl_source_pair(raw_c5),
        policy=_policy(),
    )

    assert metric_c4.status == metric_c5.status == "projected"
    assert (
        metric_c4.identity["metric_pair_signature"]
        == metric_c5.identity["metric_pair_signature"]
    )
    assert metric_c4.diagnostics["coupled_identity"] is False
    assert coupled_c4.status == coupled_c5.status == "projected"
    assert (
        coupled_c4.identity["primitive_pair_key"]
        != coupled_c5.identity["primitive_pair_key"]
    )


def test_explicit_full_square_groups_merge_equivalent_sigma5_descriptions() -> None:
    identity = np.eye(2, dtype=int)
    c4 = np.array([[2, -1], [1, 2]], dtype=int)
    c5 = np.array([[1, -2], [2, 1]], dtype=int)
    group = full_square_point_group()
    projections = []
    for index, matrix in enumerate((c4, c5)):
        raw = _raw(_match_from_column_maps(identity, matrix), raw_index=index)
        projections.append(
            project_zsl_coupled_pair(
                raw,
                reconstruct_zsl_source_pair(raw),
                policy=_policy(),
                point_group_A=group,
                point_group_B=group,
                surface_metric_tolerance=1.0e-12,
            )
        )

    assert {projection.status for projection in projections} == {"projected"}
    assert len(
        {
            tuple(projection.identity["primitive_pair_key"])
            for projection in projections
        }
    ) == 1
    assert projections[0].diagnostics["point_group_A"]["operation_count"] == 8


def test_common_right_relabeling_and_nonprimitive_repetition_preserve_key() -> None:
    identity = np.eye(2, dtype=int)
    c4 = np.array([[2, -1], [1, 2]], dtype=int)
    common_right = np.array([[1, 1], [0, 1]], dtype=int)
    source_pairs = (
        (identity, c4),
        (identity @ common_right, c4 @ common_right),
        (2 * identity, 2 * c4),
    )
    keys: list[tuple[int, ...]] = []
    repeats: list[int] = []
    for index, (source_a, source_b) in enumerate(source_pairs):
        raw = _raw(
            _match_from_column_maps(source_a, source_b),
            raw_index=index,
        )
        projection = project_zsl_coupled_pair(
            raw,
            reconstruct_zsl_source_pair(raw),
            policy=_policy(),
        )
        assert projection.status == "projected"
        keys.append(tuple(projection.identity["primitive_pair_key"]))
        repeats.append(int(projection.identity["repeat_index"]))

    assert len(set(keys)) == 1
    assert repeats[:2] == [1, 1]
    assert repeats[2] == 4


def test_proper_orientation_policy_rejects_relative_reflection() -> None:
    identity = np.eye(2, dtype=int)
    reflection = np.diag([-1, 1])
    raw = _raw(_match_from_column_maps(identity, reflection))
    reconstruction = reconstruct_zsl_source_pair(raw)

    proper = project_zsl_coupled_pair(
        raw,
        reconstruction,
        policy=_policy(orientation="proper"),
    )
    all_orientations = project_zsl_coupled_pair(
        raw,
        reconstruction,
        policy=_policy(orientation="all"),
    )

    assert proper.status == "orientation_rejected"
    assert proper.identity["relative_orientation_sign"] == -1
    assert all_orientations.status == "projected"


class FakeGenerator:
    def __init__(self, **settings: object) -> None:
        self.settings = settings

    def __call__(self, film_vectors, substrate_vectors):
        del film_vectors, substrate_vectors
        identity = np.eye(2, dtype=int)
        c4 = np.array([[2, -1], [1, 2]], dtype=int)
        c5 = np.array([[1, -2], [2, 1]], dtype=int)
        return [
            _match_from_column_maps(identity, c4),
            _match_from_column_maps(identity, c5),
        ]


def test_projection_suite_reports_distinct_count_semantics(tmp_path: Path) -> None:
    pair = LatticePair2D(
        name="equal_square",
        A=np.eye(2),
        B=np.eye(2),
        comment="Equal square projection fixture.",
    )
    capture_root = tmp_path / "capture"
    capture_zsl_sources(
        output_root=capture_root,
        repository_root=Path(__file__).resolve().parents[3],
        command=("python", "-m", "benchmarks.run_zsl_source_capture"),
        pairs=(pair,),
        max_areas=(10.0,),
        generator_factory=FakeGenerator,
        tool_version="test-version",
    )

    projection_root = tmp_path / "projection"
    artifacts = project_captured_zsl_sources(
        capture_root=capture_root,
        output_root=projection_root,
        repository_root=Path(__file__).resolve().parents[3],
        command=("python", "-m", "benchmarks.run_zsl_projection"),
    )

    metric_records = [
        json.loads(line)
        for line in artifacts.metric_projections.read_text(
            encoding="utf-8"
        ).splitlines()
    ]
    coupled_records = [
        json.loads(line)
        for line in artifacts.coupled_projections.read_text(
            encoding="utf-8"
        ).splitlines()
    ]
    summary = json.loads(artifacts.summary.read_text(encoding="utf-8"))

    assert len(metric_records) == len(coupled_records) == 2
    assert summary["scientific_claim_evaluated"] is False
    assert summary["raw_match_count"] == 2
    assert summary["unique_metric_pair_signature_count"] == 1
    assert summary["unique_source_pair_count"] == 2
    assert summary["unique_primitive_coupled_pair_key_count"] == 2
    assert summary["surface_group_modes"] == {"equal_square": "identity_only"}
    assert {artifact["path"] for artifact in json.loads(
        artifacts.manifest.read_text(encoding="utf-8")
    )["artifacts"]} == {
        "zsl_metric_projection.jsonl",
        "zsl_coupled_projection.jsonl",
        "projection_summary.json",
    }


def test_point_group_file_loader_preserves_explicit_fixture_groups(
    tmp_path: Path,
) -> None:
    group = full_square_point_group()
    path = tmp_path / "groups.json"
    path.write_text(
        json.dumps(
            {
                "schema": POINT_GROUP_FILE_SCHEMA,
                "fixtures": {
                    "equal_square": {
                        "A": [operation.tolist() for operation in group],
                        "B": [operation.tolist() for operation in group],
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    loaded = load_point_group_file(path)

    assert set(loaded) == {"equal_square"}
    assert len(loaded["equal_square"][0]) == 8
    assert len(loaded["equal_square"][1]) == 8
