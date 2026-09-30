from __future__ import annotations

from pathlib import Path

from benchmarks.benchmarks._performance_support import (
    environment_metadata,
    peak_process_bytes,
    profile_callable,
    selected_workloads,
    summarize_measurements,
    validate_measurement_equivalence,
)


def test_shared_summary_supports_detailed_and_compact_report_shapes() -> None:
    timing = (
        {
            "elapsed_seconds": 1.0,
            "peak_process_bytes": 1000,
            "qualification": {"digest": "same"},
        },
        {
            "elapsed_seconds": 3.0,
            "peak_process_bytes": 3000,
            "qualification": {"digest": "same"},
        },
    )
    memory = (
        {
            "elapsed_seconds": 2.0,
            "peak_python_bytes": 200,
            "qualification": {"digest": "same"},
        },
    )

    assert validate_measurement_equivalence(
        (*timing, *memory),
        correctness_fields=("digest",),
    ) == {"digest": "same"}

    detailed = summarize_measurements(timing, memory_measurements=memory)
    assert detailed["timing_sample_count"] == 2
    assert detailed["elapsed_seconds"]["sample_standard_deviation"] > 0.0
    assert detailed["peak_python_bytes"] == {
        "sample_count": 1,
        "minimum": 200,
        "median": 200,
        "maximum": 200,
    }

    compact = summarize_measurements(
        timing,
        memory_measurements=memory,
        include_timing_sample_count=False,
        include_standard_deviation=False,
        detailed_peak_distributions=False,
    )
    assert set(compact["elapsed_seconds"]) == {
        "minimum",
        "median",
        "mean",
        "maximum",
    }
    assert compact["peak_python_bytes"] == {"median": 200}
    assert compact["peak_process_bytes"] == {"median": 2000.0}


def test_shared_workload_selection_preserves_request_order() -> None:
    workloads = ({"id": "a"}, {"id": "b"}, {"id": "c"})
    selected = selected_workloads(
        workloads,
        ("c", "a"),
        identifier=lambda workload: workload["id"],
        label="test workload",
    )
    assert selected == (workloads[2], workloads[0])


def test_shared_profile_support_writes_hashed_artifact(tmp_path: Path) -> None:
    artifact = tmp_path / "profile.prof"
    evidence = profile_callable(
        lambda: {
            "elapsed_seconds": 0.0,
            "qualification": {"digest": "same"},
        },
        artifact_path=artifact,
        repository_root=Path.cwd(),
        production_root=None,
        top_n=5,
    )

    assert evidence["measurement"]["qualification"] == {"digest": "same"}
    assert evidence["artifact"] == str(artifact.resolve())
    assert isinstance(evidence["artifact_sha256"], str)
    assert len(evidence["artifact_sha256"]) == 64
    assert evidence["overall_top_cumulative"]


def test_shared_environment_and_process_memory_are_interpretable() -> None:
    environment = environment_metadata()
    assert environment["python_executable"]
    assert environment["python_version"]
    assert environment["numpy_version"]
    assert set(environment["thread_environment"]) == {
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
        "NUMEXPR_NUM_THREADS",
        "BLIS_NUM_THREADS",
    }
    peak = peak_process_bytes()
    assert peak is None or peak > 0
