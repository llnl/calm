from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from benchmarks.benchmarks.claims.claim_ids import ClaimStatus
from benchmarks.benchmarks.claims.zsl.oracle_comparison import (
    ZSLOracleComparisonConfig,
    run_zsl_oracle_comparison,
)
from benchmarks.benchmarks.run_zsl_oracle_comparison import main


@dataclass
class FakeZSLMatch:
    film_sl_vectors: np.ndarray
    substrate_sl_vectors: np.ndarray
    film_vectors: np.ndarray
    substrate_vectors: np.ndarray
    film_transformation: np.ndarray
    substrate_transformation: np.ndarray

    @property
    def match_area(self) -> float:
        return float(np.linalg.norm(np.cross(*self.film_sl_vectors)))

    @property
    def match_transformation(self) -> np.ndarray:
        return np.eye(3)


class IdentityOnlyGenerator:
    def __init__(self, **settings: object) -> None:
        self.settings = settings

    def __call__(self, film_vectors, substrate_vectors):
        identity = np.eye(2, dtype=int)
        return [
            FakeZSLMatch(
                film_sl_vectors=np.asarray(film_vectors, dtype=float),
                substrate_sl_vectors=np.asarray(substrate_vectors, dtype=float),
                film_vectors=np.asarray(film_vectors, dtype=float),
                substrate_vectors=np.asarray(substrate_vectors, dtype=float),
                film_transformation=identity,
                substrate_transformation=identity,
            )
        ]


def test_zsl_oracle_comparison_reports_complete_k1_identity_inventory(
    tmp_path: Path,
) -> None:
    output = tmp_path / "c7"
    artifacts = run_zsl_oracle_comparison(
        output_root=output,
        repository_root=Path(__file__).resolve().parents[3],
        command=("python-test", "c7"),
        config=ZSLOracleComparisonConfig(
            profile="smoke",
            case_ids=("equal_square_k5",),
            k_max_override=1,
            directionality="unidirectional",
        ),
        generator_factory=IdentityOnlyGenerator,
        tool_version="test-zsl",
    )

    assert artifacts.result.status is ClaimStatus.DESCRIPTIVE_ONLY
    summary = json.loads(artifacts.summary.read_text(encoding="utf-8"))
    comparison = summary["comparisons"][0]
    assert comparison["oracle_key_count"] == 1
    assert comparison["calm_production_matches_oracle"] is True
    assert comparison["zsl_exact_key_count"] == 1
    assert comparison["zsl_exact_reference_recall"] == 1.0
    assert comparison["zsl_exact_reference_precision"] == 1.0
    assert comparison["zsl_exact_missing_key_count"] == 0
    assert comparison["zsl_exact_extra_key_count"] == 0
    assert artifacts.raw_matches.read_text(encoding="utf-8").count("\n") == 1


def test_zsl_oracle_comparison_keeps_missing_sigma5_descriptive(
    tmp_path: Path,
) -> None:
    output = tmp_path / "c7_missing"
    artifacts = run_zsl_oracle_comparison(
        output_root=output,
        repository_root=Path(__file__).resolve().parents[3],
        command=("python-test", "c7"),
        config=ZSLOracleComparisonConfig(
            profile="smoke",
            case_ids=("equal_square_k5",),
            directionality="unidirectional",
        ),
        generator_factory=IdentityOnlyGenerator,
        tool_version="test-zsl",
    )

    assert artifacts.result.status is ClaimStatus.DESCRIPTIVE_ONLY
    comparisons = [
        json.loads(line)
        for line in artifacts.comparisons.read_text(encoding="utf-8").splitlines()
    ]
    assert len(comparisons) == 1
    comparison = comparisons[0]
    assert comparison["oracle_key_count"] == 2
    assert comparison["zsl_exact_key_count"] == 1
    assert comparison["zsl_exact_reference_recall"] == 0.5
    assert len(comparison["zsl_exact_missing_keys"]) == 1
    observations = [
        json.loads(line)
        for line in artifacts.key_observations.read_text(encoding="utf-8").splitlines()
    ]
    assert {row["classification"] for row in observations} == {
        "oracle_key_generated_under_exact_gate",
        "oracle_key_not_generated",
    }


def test_zsl_oracle_cli_uses_external_generator_lazily(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    from benchmarks.benchmarks.claims.zsl import oracle_comparison

    monkeypatch.setattr(
        oracle_comparison,
        "default_generator_factory",
        IdentityOnlyGenerator,
    )
    monkeypatch.setattr(oracle_comparison, "pymatgen_version", lambda: "test-zsl")
    output = tmp_path / "cli"

    assert main(
        [
            "--outdir",
            str(output),
            "--profile",
            "smoke",
            "--case",
            "equal_square_k5",
            "--k-max",
            "1",
            "--directionality",
            "unidirectional",
        ]
    ) == 0
    assert "C7 status: descriptive_only" in capsys.readouterr().out
    assert (output / "zsl_oracle_summary.json").is_file()
