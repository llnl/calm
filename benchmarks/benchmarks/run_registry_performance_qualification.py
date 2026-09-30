"""Qualify prepared registry-search geometry against one-shot reconstruction."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sys
import time
import tracemalloc
from types import ModuleType
from typing import Any, Mapping, Sequence

import numpy as np

from calm.interface.building._kernel import (
    build_interface_atoms,
    build_prepared_interface_atoms,
    prepare_interface_atoms,
)
from calm.interface.refinement.registry import monte_carlo_registry_search

from ._performance_support import (
    environment_metadata,
    peak_process_bytes,
    profile_callable,
    run_json_worker,
    selected_workloads,
    sha256_path,
    source_metadata,
    summarize_measurements,
    validate_measurement_equivalence,
    write_json_report,
)


REPORT_SCHEMA = "calm.registry_performance_qualification/v2"
MATRIX_SCHEMA = "calm.registry_performance_matrix/v2"
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MATRIX_PATH = (
    REPOSITORY_ROOT / "engineering" / "qualification" / "registry-performance-matrix.json"
)
_MODES = ("rebuild_each_evaluation", "prepared_once")


@dataclass(frozen=True)
class RegistryPerformanceWorkload:
    benchmark_id: str
    atoms_per_slab: int
    n_steps: int
    step_scale: float
    seed: int
    profile: bool
    purpose: str
    expected: Mapping[str, Any]


@dataclass(frozen=True)
class RegistryPerformanceMatrix:
    path: Path
    sha256: str
    default_repeats: int
    default_memory_repeats: int
    correctness_fields: tuple[str, ...]
    diagnostic_fields: tuple[str, ...]
    workloads: tuple[RegistryPerformanceWorkload, ...]


class _Cell:
    def __init__(self, value: Any) -> None:
        self.array = np.asarray(value, dtype=float)

    def __array__(self, dtype=None):
        return np.asarray(self.array, dtype=dtype)


class _BenchmarkAtoms:
    def __init__(self, positions: Any, cell: Any) -> None:
        self.positions = np.asarray(positions, dtype=float)
        self.cell = _Cell(cell)
        self.pbc = (False, False, False)
        self.calc: Any | None = None

    def copy(self):
        copied = _BenchmarkAtoms(self.positions.copy(), self.cell.array.copy())
        copied.pbc = tuple(self.pbc)
        return copied

    def __len__(self) -> int:
        return int(self.positions.shape[0])

    def set_cell(self, cell: Any, scale_atoms: bool = False) -> None:
        if scale_atoms:
            raise ValueError("benchmark fixture does not support scaled cell updates")
        self.cell = _Cell(cell)

    def translate(self, vector: Any) -> None:
        self.positions = self.positions + np.asarray(vector, dtype=float)

    def get_cell(self) -> np.ndarray:
        return self.cell.array.copy()

    def get_scaled_positions(self, wrap: bool = False) -> np.ndarray:
        del wrap
        cell = self.cell.array
        determinant = float(cell[0, 0] * cell[1, 1] - cell[0, 1] * cell[1, 0])
        positions = self.positions
        scaled = np.empty_like(positions)
        scaled[:, 0] = (
            positions[:, 0] * cell[1, 1] - positions[:, 1] * cell[1, 0]
        ) / determinant
        scaled[:, 1] = (
            -positions[:, 0] * cell[0, 1] + positions[:, 1] * cell[0, 0]
        ) / determinant
        scaled[:, 2] = positions[:, 2] / cell[2, 2]
        return scaled

    def set_scaled_positions(self, scaled: Any) -> None:
        values = np.asarray(scaled, dtype=float)
        cell = self.cell.array
        positions = np.empty_like(values)
        positions[:, 0] = values[:, 0] * cell[0, 0] + values[:, 1] * cell[1, 0]
        positions[:, 1] = values[:, 0] * cell[0, 1] + values[:, 1] * cell[1, 1]
        positions[:, 2] = values[:, 2] * cell[2, 2]
        self.positions = positions

    def __iadd__(self, other):
        self.positions = np.vstack([self.positions, other.positions])
        return self

    def get_potential_energy(self) -> float:
        if self.calc is None:
            raise RuntimeError("benchmark atoms require one attached calculator")
        return float(self.calc.get_potential_energy(self))


@dataclass(frozen=True)
class _DeterministicCalculator:
    first_upper_index: int
    target: tuple[float, float] = (0.37, 0.61)

    def get_potential_energy(self, atoms: _BenchmarkAtoms) -> float:
        scaled = atoms.get_scaled_positions(wrap=False)
        translation = np.asarray(scaled[self.first_upper_index, :2], dtype=float)
        target = np.asarray(self.target, dtype=float)
        delta = (translation - target + 0.5) % 1.0 - 0.5
        area = float(np.linalg.norm(np.cross(atoms.cell.array[0], atoms.cell.array[1])))
        return area * float(delta @ delta + 0.001)


def _positive_int(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return int(value)


def _digest(value: object) -> str:
    encoded = json.dumps(value, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def load_registry_performance_matrix(
    path: str | Path = DEFAULT_MATRIX_PATH,
) -> RegistryPerformanceMatrix:
    matrix_path = Path(path).expanduser().resolve()
    payload = json.loads(matrix_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema") != MATRIX_SCHEMA:
        raise ValueError("unsupported registry performance matrix")
    raw_workloads = payload.get("workloads")
    if not isinstance(raw_workloads, list) or not raw_workloads:
        raise ValueError("registry workloads must be a nonempty list")
    workloads: list[RegistryPerformanceWorkload] = []
    identifiers: set[str] = set()
    for raw in raw_workloads:
        if not isinstance(raw, dict):
            raise TypeError("registry workload must be an object")
        identifier = str(raw.get("id", "")).strip()
        if not identifier or identifier in identifiers:
            raise ValueError(f"invalid or duplicate registry workload {identifier!r}")
        identifiers.add(identifier)
        expected = raw.get("expected")
        if not isinstance(expected, dict):
            raise TypeError(f"registry workload {identifier!r} expected must be an object")
        workloads.append(
            RegistryPerformanceWorkload(
                benchmark_id=identifier,
                atoms_per_slab=_positive_int("atoms_per_slab", raw.get("atoms_per_slab")),
                n_steps=_positive_int("n_steps", raw.get("n_steps")),
                step_scale=float(raw.get("step_scale")),
                seed=int(raw.get("seed")),
                profile=bool(raw.get("profile", False)),
                purpose=str(raw.get("purpose", "")).strip(),
                expected=dict(expected),
            )
        )
    correctness = payload.get("correctness_fields")
    if not isinstance(correctness, list) or not correctness:
        raise ValueError("correctness_fields must be a nonempty list")
    diagnostics = payload.get("diagnostic_fields")
    if not isinstance(diagnostics, list) or not diagnostics:
        raise ValueError("diagnostic_fields must be a nonempty list")
    correctness_fields = tuple(str(value) for value in correctness)
    diagnostic_fields = tuple(str(value) for value in diagnostics)
    if len(set(correctness_fields)) != len(correctness_fields):
        raise ValueError("correctness_fields must be unique")
    if len(set(diagnostic_fields)) != len(diagnostic_fields):
        raise ValueError("diagnostic_fields must be unique")
    if set(correctness_fields) & set(diagnostic_fields):
        raise ValueError("correctness_fields and diagnostic_fields must be disjoint")
    for workload in workloads:
        if set(workload.expected) != set(correctness_fields):
            raise ValueError(
                f"registry workload {workload.benchmark_id!r} expected fields "
                "must match correctness_fields"
            )
    return RegistryPerformanceMatrix(
        path=matrix_path,
        sha256=sha256_path(matrix_path),
        default_repeats=_positive_int("default_repeats", payload.get("default_repeats")),
        default_memory_repeats=_positive_int(
            "default_memory_repeats", payload.get("default_memory_repeats")
        ),
        correctness_fields=correctness_fields,
        diagnostic_fields=diagnostic_fields,
        workloads=tuple(workloads),
    )


@contextmanager
def _benchmark_ase_adapter():
    name = "calm.structure.ase_adapter"
    previous = sys.modules.get(name)
    module = ModuleType(name)

    def make_supercell_col(atoms, matrix, *, wrap=True):
        del wrap
        if not np.array_equal(np.asarray(matrix, dtype=int), np.eye(3, dtype=int)):
            raise ValueError("registry benchmark supports identity supercells only")
        return atoms.copy()

    def wrap_xy_clamp_z(atoms, *, eps=1.0e-8):
        scaled = atoms.get_scaled_positions(wrap=False)
        scaled[:, :2] = np.mod(scaled[:, :2], 1.0)
        scaled[:, 2] = np.clip(scaled[:, 2], 0.0, 1.0 - eps)
        atoms.set_scaled_positions(scaled)

    module.make_supercell_col = make_supercell_col
    module.wrap_xy_clamp_z = wrap_xy_clamp_z
    sys.modules[name] = module
    try:
        yield
    finally:
        if previous is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = previous


def _fixture(workload: RegistryPerformanceWorkload):
    rng = np.random.Generator(np.random.PCG64(20260729))
    cell = np.asarray([[20.0, 0.0, 0.0], [3.0, 17.0, 0.0], [0.0, 0.0, 12.0]])
    count = workload.atoms_per_slab
    lower = np.column_stack(
        [rng.random(count) * 20.0, rng.random(count) * 17.0, rng.random(count) * 3.0]
    )
    upper = np.column_stack(
        [rng.random(count) * 20.0, rng.random(count) * 17.0, rng.random(count) * 3.0]
    )
    upper[0, :2] = 0.0
    return _BenchmarkAtoms(lower, cell), _BenchmarkAtoms(upper, cell)


def _build_kwargs() -> dict[str, Any]:
    return {
        "N_A3": np.eye(3, dtype=int),
        "N_B3": np.eye(3, dtype=int),
        "R_A3": np.eye(3),
        "R_B3": np.eye(3),
        "F_A": np.eye(3),
        "F_B": np.eye(3),
        "z_padding": 1.5,
        "vacuum_padding": 2.0,
    }


def _qualification(result, evaluations: int, atom_count: int) -> dict[str, Any]:
    proposals = result.proposal_trace or ()
    proposal_values = [
        [float(value).hex() for value in record.proposed_translation]
        for record in proposals
    ]
    trajectory = [
        [record.accepted, *[float(value).hex() for value in record.current_translation]]
        for record in proposals
    ]
    score_trace = [
        [
            record.accepted,
            format(float(record.current_score), ".10e"),
            format(float(record.best_score), ".10e"),
        ]
        for record in proposals
    ]
    return {
        "observed_proposal_trace_sha256": _digest(proposal_values),
        "proposal_count": len(proposals),
        "trajectory_sha256": _digest(trajectory),
        "score_trace_sha256": _digest(score_trace),
        "best_translation_hex": [float(value).hex() for value in result.translation],
        "best_score_quantized": format(float(result.score), ".10e"),
        "n_steps": int(result.n_steps),
        "n_accepted": int(result.n_accepted),
        "objective_evaluations": int(evaluations),
        "atom_count": int(atom_count),
    }


def _portable_oracle_mismatches(
    expected: Mapping[str, Any],
    qualification: Mapping[str, Any],
) -> dict[str, tuple[Any, Any]]:
    """Return mismatches for matrix-owned portable correctness fields only."""

    return {
        key: (expected_value, qualification.get(key))
        for key, expected_value in expected.items()
        if qualification.get(key) != expected_value
    }


def run_workload_trial(
    workload: RegistryPerformanceWorkload,
    *,
    mode: str,
    measure_memory: bool,
) -> dict[str, Any]:
    if mode not in _MODES:
        raise ValueError(f"unsupported registry mode {mode!r}")
    lower, upper = _fixture(workload)
    kwargs = _build_kwargs()
    calculator = _DeterministicCalculator(first_upper_index=workload.atoms_per_slab)
    evaluations = 0
    if measure_memory:
        tracemalloc.start()
    started = time.perf_counter()
    with _benchmark_ase_adapter():
        prepared = None
        if mode == "prepared_once":
            prepared = prepare_interface_atoms(lower, upper, **kwargs)
        area = float(np.linalg.norm(np.cross(lower.cell.array[0], lower.cell.array[1])))

        def objective(translation: np.ndarray) -> float:
            nonlocal evaluations
            evaluations += 1
            translation_frac = (float(translation[0]), float(translation[1]))
            if prepared is None:
                built = build_interface_atoms(
                    lower,
                    upper,
                    translation_frac=translation_frac,
                    **kwargs,
                )
            else:
                built = build_prepared_interface_atoms(
                    prepared,
                    translation_frac=translation_frac,
                )
            built.atoms.calc = calculator
            return float(built.atoms.get_potential_energy()) / area

        result = monte_carlo_registry_search(
            objective,
            n_steps=workload.n_steps,
            step_scale=workload.step_scale,
            temperature=0.0,
            seed=workload.seed,
            x0=(0.0, 0.0),
            keep_trace=True,
            score_units="eV_per_A2",
        )
    elapsed = time.perf_counter() - started
    peak_python = None
    if measure_memory:
        _, peak_python = tracemalloc.get_traced_memory()
        tracemalloc.stop()
    qualification = _qualification(
        result,
        evaluations,
        atom_count=2 * workload.atoms_per_slab,
    )
    expected = workload.expected
    mismatches = _portable_oracle_mismatches(expected, qualification)
    if mismatches:
        raise RuntimeError(
            f"registry oracle mismatch for {workload.benchmark_id}: {mismatches}"
        )
    return {
        "mode": mode,
        "elapsed_seconds": float(elapsed),
        "peak_python_bytes": peak_python,
        "peak_process_bytes": peak_process_bytes(),
        "qualification": qualification,
        "diagnostics": {
            "geometry_preparations": 1 if prepared is not None else evaluations,
            "calculator_constructions": 1,
        },
    }


def _registry_worker(
    workload: RegistryPerformanceWorkload,
    mode: str,
    measure_memory: bool,
) -> dict[str, Any]:
    return run_json_worker(
        module="benchmarks.run_registry_performance_qualification",
        payload={
            "benchmark_id": workload.benchmark_id,
            "mode": mode,
            "measure_memory": measure_memory,
        },
        repository_root=REPOSITORY_ROOT,
        error_label="registry worker",
    )


def _registry_mode_result(
    mode: str,
    timing: Sequence[Mapping[str, Any]],
    memory: Sequence[Mapping[str, Any]],
    correctness_fields: Sequence[str],
) -> dict[str, Any]:
    all_measurements = tuple(timing) + tuple(memory)
    return {
        "mode": mode,
        "correctness_signature": validate_measurement_equivalence(
            all_measurements,
            correctness_fields=correctness_fields,
            error_prefix="registry trials changed correctness signature",
        ),
        "timing_measurements": list(timing),
        "memory_measurements": list(memory),
        "summary": summarize_measurements(
            timing,
            memory_measurements=memory,
            include_timing_sample_count=False,
            include_standard_deviation=False,
            detailed_peak_distributions=False,
        ),
    }


def _registry_profile(
    workload: RegistryPerformanceWorkload,
    mode: str,
    directory: Path,
    top: int,
) -> dict[str, Any]:
    evidence = profile_callable(
        lambda: run_workload_trial(workload, mode=mode, measure_memory=False),
        artifact_path=directory / f"{workload.benchmark_id}-{mode}.prof",
        repository_root=REPOSITORY_ROOT,
        production_root=None,
        top_n=top,
        relative_filenames=False,
    )
    return {
        "mode": mode,
        "artifact": evidence["artifact"],
        "sha256": evidence["artifact_sha256"],
        "qualification": evidence["measurement"]["qualification"],
        "top_entries": evidence["overall_top_cumulative"],
    }


def run_qualification(
    matrix: RegistryPerformanceMatrix,
    *,
    benchmark_ids: Sequence[str] = (),
    repeats: int | None = None,
    memory_repeats: int | None = None,
    measure_memory: bool = False,
    profile: bool = False,
    profile_outdir: str | Path | None = None,
    profile_top: int = 20,
    require_clean: bool = False,
) -> dict[str, Any]:
    source = source_metadata(REPOSITORY_ROOT)
    if require_clean and source["git_clean"] is not True:
        raise RuntimeError("registry performance qualification requires a clean Git tree")
    selected = selected_workloads(
        matrix.workloads,
        benchmark_ids,
        identifier=lambda workload: workload.benchmark_id,
        label="registry workload",
    )
    repeats_i = matrix.default_repeats if repeats is None else _positive_int("repeats", repeats)
    memory_i = (
        matrix.default_memory_repeats
        if memory_repeats is None
        else _positive_int("memory_repeats", memory_repeats)
    )
    reports = []
    for workload in selected:
        modes = []
        for mode in _MODES:
            timing = tuple(_registry_worker(workload, mode, False) for _ in range(repeats_i))
            memory = (
                tuple(_registry_worker(workload, mode, True) for _ in range(memory_i))
                if measure_memory
                else ()
            )
            modes.append(
                _registry_mode_result(
                    mode,
                    timing,
                    memory,
                    matrix.correctness_fields + matrix.diagnostic_fields,
                )
            )
        if modes[0]["correctness_signature"] != modes[1]["correctness_signature"]:
            raise RuntimeError(
                f"prepared registry trajectory differs for {workload.benchmark_id}"
            )
        profile_records = []
        if profile and workload.profile:
            directory = Path(profile_outdir or "build/performance/registry-profiles")
            profile_records = [
                _registry_profile(workload, mode, directory, profile_top) for mode in _MODES
            ]
        reports.append(
            {
                "benchmark_id": workload.benchmark_id,
                "purpose": workload.purpose,
                "modes": modes,
                "speedup_rebuild_over_prepared": (
                    modes[0]["summary"]["elapsed_seconds"]["median"]
                    / modes[1]["summary"]["elapsed_seconds"]["median"]
                ),
                "profiles": profile_records,
            }
        )
    return {
        "schema": REPORT_SCHEMA,
        "matrix": {
            "schema": MATRIX_SCHEMA,
            "path": str(matrix.path),
            "sha256": matrix.sha256,
        },
        "source": source,
        "environment": environment_metadata(),
        "measurement_policy": {
            "comparison": "fresh_process_rebuild_each_evaluation_vs_prepared_once",
            "timing_thresholds": "none_same_host_comparison_only",
            "calculator": "dependency_light_deterministic_translation_objective",
            "scientific_equivalence": (
                "portable_accepted_trajectory_oracle_and_same_host_exact_"
                "proposal_equivalence"
            ),
            "rejected_proposal_float_bits": "same_host_diagnostic_only",
        },
        "workloads": reports,
    }


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", default=str(DEFAULT_MATRIX_PATH))
    parser.add_argument("--out")
    parser.add_argument("--benchmark", action="append", default=[])
    parser.add_argument("--repeats", type=int)
    parser.add_argument("--memory-repeats", type=int)
    parser.add_argument("--measure-memory", action="store_true")
    parser.add_argument("--profile", action="store_true")
    parser.add_argument("--profile-outdir")
    parser.add_argument("--profile-top", type=int, default=20)
    parser.add_argument("--require-clean", action="store_true")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--worker-payload")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    matrix = load_registry_performance_matrix(args.matrix)
    if args.worker_payload:
        payload = json.loads(args.worker_payload)
        workload = next(
            item for item in matrix.workloads if item.benchmark_id == payload["benchmark_id"]
        )
        print(
            json.dumps(
                run_workload_trial(
                    workload,
                    mode=str(payload["mode"]),
                    measure_memory=bool(payload["measure_memory"]),
                ),
                separators=(",", ":"),
            )
        )
        return 0
    if args.list:
        for workload in matrix.workloads:
            print(workload.benchmark_id)
        return 0
    report = run_qualification(
        matrix,
        benchmark_ids=args.benchmark,
        repeats=args.repeats,
        memory_repeats=args.memory_repeats,
        measure_memory=args.measure_memory,
        profile=args.profile,
        profile_outdir=args.profile_outdir,
        profile_top=args.profile_top,
        require_clean=args.require_clean,
    )
    if args.out:
        write_json_report(report, args.out)
    else:
        print(json.dumps(report, indent=2, sort_keys=True) + "\n", end="")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
