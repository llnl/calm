"""Common-domain qualification for principal-strain and reduced-parameter gates.

The stage deliberately separates two questions:

1. Does CALM's metric calculation and strict principal-strain predicate agree
   with analytic strain states, including the boundary?
2. How do reduced length/angle predicates classify the *same* finite trial
   population?

The random perturbation population matches the manuscript construction: a
reference cell ``(a, b, gamma) = (3.1 A, 2.3 A, 70 deg)`` is perturbed by
independent uniform changes in both lengths and the included angle.  The stream
is seeded, chunked, and summarized at prefix checkpoints so publication-scale
runs do not require retaining every candidate in memory.
"""

from __future__ import annotations

import importlib.metadata
import math
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from ..common_metrics import airm_distance_and_strains, basis_params
from ._support import write_csv_atomic
from .claim_ids import ClaimId, ClaimStatus
from .manifest import (
    artifact_record,
    build_manifest,
    canonical_json_bytes,
    sha256_bytes,
    write_json_atomic,
)
from .schemas import ClaimResult, GateCandidate, GateDecision


GATE_DOMAIN_SUMMARY_SCHEMA = "calm.gate_domain_summary/v1"
GATE_CONFUSION_SCHEMA = "calm.gate_confusion_matrix/v1"
GATE_CONVERGENCE_SCHEMA = "calm.gate_convergence/v1"
GATE_EXAMPLE_SCHEMA = "calm.gate_disagreement_example/v1"
GATE_HISTOGRAM_EDGE_SCHEMA = "calm.principal_strain_histogram_edge/v1"
GATE_HISTOGRAM_SCHEMA = "calm.principal_strain_histogram/v1"
GATE_HISTOGRAM_SUMMARY_SCHEMA = "calm.principal_strain_histogram_summary/v1"

CALM_GATE_ID = "calm_principal_strain_v1"
TARGET_POPULATION_ID = "target_principal_strain_domain_v1"
PYMATGEN_NATIVE_UNIDIRECTIONAL_GATE_ID = (
    "pymatgen_zsl_is_same_vectors_unidirectional_v1"
)
PYMATGEN_NATIVE_BIDIRECTIONAL_GATE_ID = "pymatgen_zsl_is_same_vectors_bidirectional_v1"

DEFAULT_SEED = 20260728
DEFAULT_SAMPLE_COUNT = 100_000
DEFAULT_CHUNK_SIZE = 100_000
DEFAULT_CHECKPOINTS = (1_000, 10_000, 100_000)
DEFAULT_ABSOLUTE_ANGLE_TOLERANCES_DEG = (0.5, 1.0, 1.5)
DEFAULT_HISTOGRAM_BIN_COUNT = 200
DEFAULT_HISTOGRAM_MIN_STRAIN = -0.05
DEFAULT_HISTOGRAM_MAX_STRAIN = 0.05


@dataclass(frozen=True)
class GateDomainConfig:
    """Complete, versioned configuration for one gate-domain invocation."""

    sample_count: int = DEFAULT_SAMPLE_COUNT
    seed: int = DEFAULT_SEED
    chunk_size: int = DEFAULT_CHUNK_SIZE
    checkpoints: tuple[int, ...] = DEFAULT_CHECKPOINTS
    retained_sample_count: int = 1_000
    disagreement_examples_per_category: int = 10
    reference_a: float = 3.1
    reference_b: float = 2.3
    reference_gamma_deg: float = 70.0
    maximum_length_perturbation: float = 0.03
    maximum_angle_perturbation_deg: float = 1.5
    max_principal_strain: float = 0.03
    calm_gate_tolerance: float = 64.0 * np.finfo(float).eps
    manuscript_length_tolerance: float = 0.03
    manuscript_angle_tolerances_deg: tuple[float, ...] = (
        DEFAULT_ABSOLUTE_ANGLE_TOLERANCES_DEG
    )
    pymatgen_max_length_tol: float = 0.03
    pymatgen_max_angle_tol: float = 0.01
    boundary_inside_offset: float = 1.0e-6
    boundary_outside_offset: float = 1.0e-6
    boundary_measurement_tolerance: float = 5.0e-12
    histogram_bin_count: int = DEFAULT_HISTOGRAM_BIN_COUNT
    histogram_min_strain: float = DEFAULT_HISTOGRAM_MIN_STRAIN
    histogram_max_strain: float = DEFAULT_HISTOGRAM_MAX_STRAIN

    def __post_init__(self) -> None:
        for name in (
            "sample_count",
            "chunk_size",
            "retained_sample_count",
            "disagreement_examples_per_category",
            "histogram_bin_count",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a nonnegative integer")
        if self.sample_count <= 0:
            raise ValueError("sample_count must be positive")
        if self.chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if self.histogram_bin_count <= 0:
            raise ValueError("histogram_bin_count must be positive")
        checkpoints = tuple(int(value) for value in self.checkpoints)
        if any(value <= 0 for value in checkpoints):
            raise ValueError("checkpoints must be positive")
        if tuple(sorted(set(checkpoints))) != checkpoints:
            raise ValueError("checkpoints must be sorted and unique")
        for name in (
            "reference_a",
            "reference_b",
            "maximum_length_perturbation",
            "maximum_angle_perturbation_deg",
            "max_principal_strain",
            "calm_gate_tolerance",
            "manuscript_length_tolerance",
            "pymatgen_max_length_tol",
            "pymatgen_max_angle_tol",
            "boundary_inside_offset",
            "boundary_outside_offset",
            "boundary_measurement_tolerance",
        ):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and nonnegative")
        if not math.isfinite(float(self.histogram_min_strain)) or not math.isfinite(
            float(self.histogram_max_strain)
        ):
            raise ValueError("histogram strain bounds must be finite")
        if self.reference_a <= 0.0 or self.reference_b <= 0.0:
            raise ValueError("reference edge lengths must be positive")
        if self.histogram_min_strain >= self.histogram_max_strain:
            raise ValueError(
                "histogram_min_strain must be less than histogram_max_strain"
            )
        if not (0.0 < self.reference_gamma_deg < 180.0):
            raise ValueError("reference_gamma_deg must lie strictly between 0 and 180")
        if self.maximum_length_perturbation >= 1.0:
            raise ValueError("maximum_length_perturbation must be less than one")
        if self.maximum_angle_perturbation_deg >= min(
            self.reference_gamma_deg, 180.0 - self.reference_gamma_deg
        ):
            raise ValueError("angle perturbations must preserve a nondegenerate cell")
        angle_tolerances = tuple(
            float(value) for value in self.manuscript_angle_tolerances_deg
        )
        if not angle_tolerances:
            raise ValueError("manuscript_angle_tolerances_deg must be nonempty")
        if any(not math.isfinite(value) or value < 0.0 for value in angle_tolerances):
            raise ValueError(
                "manuscript angle tolerances must be finite and nonnegative"
            )
        if tuple(sorted(set(angle_tolerances))) != angle_tolerances:
            raise ValueError("manuscript angle tolerances must be sorted and unique")

    @property
    def effective_checkpoints(self) -> tuple[int, ...]:
        checkpoints = tuple(
            value for value in self.checkpoints if value < self.sample_count
        )
        return (*checkpoints, self.sample_count)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sample_count": int(self.sample_count),
            "seed": int(self.seed),
            "chunk_size": int(self.chunk_size),
            "checkpoints": list(self.effective_checkpoints),
            "retained_sample_count": int(self.retained_sample_count),
            "disagreement_examples_per_category": int(
                self.disagreement_examples_per_category
            ),
            "reference_cell": {
                "a": float(self.reference_a),
                "b": float(self.reference_b),
                "gamma_deg": float(self.reference_gamma_deg),
            },
            "trial_domain": {
                "relative_length_perturbation": [
                    -float(self.maximum_length_perturbation),
                    float(self.maximum_length_perturbation),
                ],
                "absolute_angle_perturbation_deg": [
                    -float(self.maximum_angle_perturbation_deg),
                    float(self.maximum_angle_perturbation_deg),
                ],
                "distribution": "independent_uniform",
                "generator": "numpy.random.Generator(PCG64)",
            },
            "calm_gate": {
                "max_abs_principal_strain": float(self.max_principal_strain),
                "roundoff_tolerance": float(self.calm_gate_tolerance),
            },
            "manuscript_reduced_parameter_gates": {
                "relative_length_tolerance": float(self.manuscript_length_tolerance),
                "absolute_angle_tolerances_deg": [
                    float(value) for value in self.manuscript_angle_tolerances_deg
                ],
            },
            "pymatgen_native_vector_gate": {
                "max_length_tol": float(self.pymatgen_max_length_tol),
                "max_angle_tol": float(self.pymatgen_max_angle_tol),
                "area_ratio_prefilter_included": False,
            },
            "boundary_suite": {
                "inside_offset": float(self.boundary_inside_offset),
                "outside_offset": float(self.boundary_outside_offset),
                "measurement_tolerance": float(self.boundary_measurement_tolerance),
            },
            "principal_strain_histogram": {
                "bin_count_per_axis": int(self.histogram_bin_count),
                "epsilon_1_range": [
                    float(self.histogram_min_strain),
                    float(self.histogram_max_strain),
                ],
                "epsilon_2_range": [
                    float(self.histogram_min_strain),
                    float(self.histogram_max_strain),
                ],
                "bin_convention": (
                    "left-inclusive, right-exclusive except the final bin, "
                    "which includes the right edge"
                ),
                "population_ids": list(histogram_population_ids(self)),
            },
        }


@dataclass(frozen=True)
class GateDomainArtifacts:
    manifest: Path
    claim_result: Path
    summary: Path
    boundary_candidates: Path
    boundary_decisions: Path
    confusion_matrix: Path
    convergence: Path
    candidate_sample: Path
    decision_sample: Path
    disagreement_examples: Path
    histogram_bin_edges: Path
    histogram_summary: Path
    histogram_files: tuple[Path, ...]
    result: ClaimResult

    @property
    def evidence_paths(self) -> tuple[Path, ...]:
        return (
            self.summary,
            self.boundary_candidates,
            self.boundary_decisions,
            self.confusion_matrix,
            self.convergence,
            self.candidate_sample,
            self.decision_sample,
            self.disagreement_examples,
            self.histogram_bin_edges,
            self.histogram_summary,
            *self.histogram_files,
        )


@dataclass
class _ConfusionCounts:
    true_positive: int = 0
    false_positive: int = 0
    false_negative: int = 0
    true_negative: int = 0

    def update(self, reference: np.ndarray, predicate: np.ndarray) -> None:
        ref = np.asarray(reference, dtype=bool)
        pred = np.asarray(predicate, dtype=bool)
        if ref.shape != pred.shape:
            raise ValueError("reference and predicate arrays must have equal shape")
        self.true_positive += int(np.count_nonzero(ref & pred))
        self.false_positive += int(np.count_nonzero(~ref & pred))
        self.false_negative += int(np.count_nonzero(ref & ~pred))
        self.true_negative += int(np.count_nonzero(~ref & ~pred))

    @property
    def total(self) -> int:
        return (
            self.true_positive
            + self.false_positive
            + self.false_negative
            + self.true_negative
        )

    def to_metrics(self) -> dict[str, Any]:
        tp = self.true_positive
        fp = self.false_positive
        fn = self.false_negative
        tn = self.true_negative
        total = self.total
        admitted = tp + fp
        target = tp + fn
        rejected_target = fp + tn
        union = tp + fp + fn

        def ratio(numerator: int, denominator: int) -> float | None:
            return None if denominator == 0 else float(numerator / denominator)

        return {
            "true_positive": tp,
            "false_positive": fp,
            "false_negative": fn,
            "true_negative": tn,
            "total": total,
            "accepted_fraction": ratio(admitted, total),
            "target_fraction": ratio(target, total),
            "precision": ratio(tp, admitted),
            "recall": ratio(tp, target),
            "false_positive_rate": ratio(fp, rejected_target),
            "jaccard": ratio(tp, union),
        }


def column_basis_from_parameters(a: float, b: float, gamma_deg: float) -> np.ndarray:
    """Return a right-handed 2D column basis from cell parameters."""

    a_value = float(a)
    b_value = float(b)
    gamma_value = float(gamma_deg)
    if a_value <= 0.0 or b_value <= 0.0:
        raise ValueError("edge lengths must be positive")
    if not (0.0 < gamma_value < 180.0):
        raise ValueError("included angle must lie strictly between 0 and 180")
    gamma = math.radians(gamma_value)
    return np.array(
        [
            [a_value, b_value * math.cos(gamma)],
            [0.0, b_value * math.sin(gamma)],
        ],
        dtype=float,
    )


def _principal_stretch_map(
    epsilon_1: float,
    epsilon_2: float,
    axis_angle_deg: float,
) -> np.ndarray:
    theta = math.radians(float(axis_angle_deg))
    cosine = math.cos(theta)
    sine = math.sin(theta)
    rotation = np.array([[cosine, -sine], [sine, cosine]], dtype=float)
    stretches = np.diag([math.exp(float(epsilon_1)), math.exp(float(epsilon_2))])
    return rotation @ stretches @ rotation.T


def _calm_admitted(
    max_abs_principal_strain: Any, config: GateDomainConfig
) -> np.ndarray:
    values = np.asarray(max_abs_principal_strain, dtype=float)
    return values <= config.max_principal_strain + config.calm_gate_tolerance


def _vector_angle_batch(first: np.ndarray, second: np.ndarray) -> np.ndarray:
    dot = np.einsum("ij,ij->i", first, second)
    cross = first[:, 0] * second[:, 1] - first[:, 1] * second[:, 0]
    return np.arctan2(np.abs(cross), dot)


def _norm_batch(vectors: np.ndarray) -> np.ndarray:
    return np.sqrt(np.einsum("ij,ij->i", vectors, vectors))


def reduce_vectors_batch(vector_sets: Any, *, max_steps: int = 128) -> np.ndarray:
    """Vectorized replica of pymatgen ZSL ``reduce_vectors``.

    The operation order and strict comparisons follow the current
    ``pymatgen.analysis.interfaces.zsl.reduce_vectors`` source contract.
    Input and output use shape ``(n, 2, d)`` with ``d >= 2``.
    """

    values = np.asarray(vector_sets, dtype=float)
    if values.ndim != 3 or values.shape[1] != 2 or values.shape[2] < 2:
        raise ValueError("vector_sets must have shape (n, 2, d) with d >= 2")
    if not np.isfinite(values).all():
        raise ValueError("vector_sets must contain only finite values")
    first = values[:, 0, :].copy()
    second = values[:, 1, :].copy()
    count = values.shape[0]

    for _ in range(max_steps):
        remaining = np.ones(count, dtype=bool)
        changed = np.zeros(count, dtype=bool)

        mask = remaining & (np.einsum("ij,ij->i", first, second) < 0.0)
        second[mask] *= -1.0
        remaining[mask] = False
        changed[mask] = True

        norm_first = _norm_batch(first)
        norm_second = _norm_batch(second)
        mask = remaining & (norm_first > norm_second)
        if np.any(mask):
            temporary = first[mask].copy()
            first[mask] = second[mask]
            second[mask] = temporary
        remaining[mask] = False
        changed[mask] = True

        norm_second = _norm_batch(second)
        mask = remaining & (norm_second > _norm_batch(second + first))
        second[mask] += first[mask]
        remaining[mask] = False
        changed[mask] = True

        norm_second = _norm_batch(second)
        mask = remaining & (norm_second > _norm_batch(second - first))
        second[mask] -= first[mask]
        changed[mask] = True

        if not np.any(changed):
            return np.stack((first, second), axis=1)

    raise RuntimeError("pymatgen-compatible vector reduction did not converge")


def pymatgen_native_gate_batch(
    reference_vector_set: Any,
    trial_vector_sets: Any,
    *,
    max_length_tol: float,
    max_angle_tol: float,
    bidirectional: bool,
) -> np.ndarray:
    """Evaluate the current pymatgen ZSL vector predicate on common candidates."""

    reference = np.asarray(reference_vector_set, dtype=float)
    trials = np.asarray(trial_vector_sets, dtype=float)
    if reference.ndim != 2 or reference.shape[0] != 2:
        raise ValueError("reference_vector_set must have shape (2, d)")
    if trials.ndim != 3 or trials.shape[1:] != reference.shape:
        raise ValueError("trial_vector_sets must have shape (n, 2, d)")
    reference_reduced = reduce_vectors_batch(reference[np.newaxis, :, :])[0]
    trial_reduced = reduce_vectors_batch(trials)

    reference_norms = np.linalg.norm(reference_reduced, axis=1)
    trial_norms = np.linalg.norm(trial_reduced, axis=2)
    reference_angle = float(
        _vector_angle_batch(
            reference_reduced[0][np.newaxis, :],
            reference_reduced[1][np.newaxis, :],
        )[0]
    )
    trial_angles = _vector_angle_batch(trial_reduced[:, 0], trial_reduced[:, 1])

    forward = (
        (np.abs(trial_norms[:, 0] / reference_norms[0] - 1.0) <= max_length_tol)
        & (np.abs(trial_norms[:, 1] / reference_norms[1] - 1.0) <= max_length_tol)
        & (np.abs(trial_angles / reference_angle - 1.0) <= max_angle_tol)
    )
    if not bidirectional:
        return forward
    reverse = (
        (np.abs(reference_norms[0] / trial_norms[:, 0] - 1.0) <= max_length_tol)
        & (np.abs(reference_norms[1] / trial_norms[:, 1] - 1.0) <= max_length_tol)
        & (np.abs(reference_angle / trial_angles - 1.0) <= max_angle_tol)
    )
    return forward | reverse


def manuscript_gate_id(angle_tolerance_deg: float) -> str:
    token = f"{float(angle_tolerance_deg):g}".replace(".", "p")
    return f"manuscript_reduced_parameter_abs_angle_{token}deg_v1"


def histogram_population_ids(config: GateDomainConfig) -> tuple[str, ...]:
    """Return the deterministic publication-histogram population order."""

    return (
        TARGET_POPULATION_ID,
        CALM_GATE_ID,
        *(
            manuscript_gate_id(angle)
            for angle in config.manuscript_angle_tolerances_deg
        ),
    )


def histogram_population_label(
    config: GateDomainConfig,
    population_id: str,
) -> str:
    """Return a reader-facing label for one histogram population."""

    if population_id == TARGET_POPULATION_ID:
        return (
            "Target principal-strain domain: "
            f"max |principal strain| <= {config.max_principal_strain:g}"
        )
    return _gate_labels(config)[population_id]


def histogram_population_filename(
    config: GateDomainConfig,
    population_id: str,
) -> str:
    """Return the stable portable CSV filename for one histogram population."""

    if population_id == TARGET_POPULATION_ID:
        return "principal_strain_histogram_target.csv"
    if population_id == CALM_GATE_ID:
        return "principal_strain_histogram_calm.csv"
    for angle in config.manuscript_angle_tolerances_deg:
        if population_id == manuscript_gate_id(angle):
            token = f"{float(angle):.1f}".replace(".", "p")
            return f"principal_strain_histogram_reduced_{token}deg.csv"
    raise KeyError(population_id)


def _gate_labels(config: GateDomainConfig) -> dict[str, str]:
    labels = {
        CALM_GATE_ID: (
            f"CALM max |principal strain| <= {config.max_principal_strain:g}"
        ),
        PYMATGEN_NATIVE_UNIDIRECTIONAL_GATE_ID: (
            "pymatgen ZSL is_same_vectors (unidirectional)"
        ),
        PYMATGEN_NATIVE_BIDIRECTIONAL_GATE_ID: (
            "pymatgen ZSL is_same_vectors (bidirectional)"
        ),
    }
    for angle in config.manuscript_angle_tolerances_deg:
        labels[manuscript_gate_id(angle)] = (
            "Manuscript reduced-parameter gate: "
            f"length <= {100.0 * config.manuscript_length_tolerance:g}% and "
            f"|delta gamma| <= {angle:g} deg"
        )
    return labels


def _gate_thresholds(config: GateDomainConfig, gate_id: str) -> dict[str, Any]:
    if gate_id == CALM_GATE_ID:
        return {
            "max_abs_principal_strain": float(config.max_principal_strain),
            "roundoff_tolerance": float(config.calm_gate_tolerance),
        }
    if gate_id == PYMATGEN_NATIVE_UNIDIRECTIONAL_GATE_ID:
        return {
            "max_length_tol": float(config.pymatgen_max_length_tol),
            "max_angle_tol": float(config.pymatgen_max_angle_tol),
            "bidirectional": False,
        }
    if gate_id == PYMATGEN_NATIVE_BIDIRECTIONAL_GATE_ID:
        return {
            "max_length_tol": float(config.pymatgen_max_length_tol),
            "max_angle_tol": float(config.pymatgen_max_angle_tol),
            "bidirectional": True,
        }
    for angle in config.manuscript_angle_tolerances_deg:
        if gate_id == manuscript_gate_id(angle):
            return {
                "max_relative_length_change": float(config.manuscript_length_tolerance),
                "max_absolute_angle_change_deg": float(angle),
            }
    raise KeyError(gate_id)


def _single_candidate_measurements(
    basis_a: np.ndarray,
    basis_b: np.ndarray,
) -> dict[str, Any]:
    gram_a = basis_a.T @ basis_a
    gram_b = basis_b.T @ basis_b
    d_cell, d_area, d_shape, strains = airm_distance_and_strains(gram_a, gram_b)
    a_a, b_a, gamma_a = basis_params(basis_a)
    a_b, b_b, gamma_b = basis_params(basis_b)
    return {
        "principal_strain_1": float(strains[0]),
        "principal_strain_2": float(strains[1]),
        "max_abs_principal_strain": float(np.max(np.abs(strains))),
        "d_cell": float(d_cell),
        "d_area": float(d_area),
        "d_shape": float(d_shape),
        "relative_length_change_a": float(a_b / a_a - 1.0),
        "relative_length_change_b": float(b_b / b_a - 1.0),
        "absolute_angle_change_deg": float(abs(gamma_b - gamma_a)),
        "reference_gamma_deg": float(gamma_a),
        "trial_gamma_deg": float(gamma_b),
    }


def _single_gate_decisions(
    candidate: GateCandidate,
    config: GateDomainConfig,
) -> tuple[GateDecision, ...]:
    basis_a = np.asarray(candidate.basis_A, dtype=float)
    basis_b = np.asarray(candidate.basis_B, dtype=float)
    measurements = _single_candidate_measurements(basis_a, basis_b)
    trial_rows = basis_b.T[np.newaxis, :, :]
    reference_rows = basis_a.T

    decisions: dict[str, bool] = {
        CALM_GATE_ID: bool(
            _calm_admitted(measurements["max_abs_principal_strain"], config)
        ),
        PYMATGEN_NATIVE_UNIDIRECTIONAL_GATE_ID: bool(
            pymatgen_native_gate_batch(
                reference_rows,
                trial_rows,
                max_length_tol=config.pymatgen_max_length_tol,
                max_angle_tol=config.pymatgen_max_angle_tol,
                bidirectional=False,
            )[0]
        ),
        PYMATGEN_NATIVE_BIDIRECTIONAL_GATE_ID: bool(
            pymatgen_native_gate_batch(
                reference_rows,
                trial_rows,
                max_length_tol=config.pymatgen_max_length_tol,
                max_angle_tol=config.pymatgen_max_angle_tol,
                bidirectional=True,
            )[0]
        ),
    }
    for angle in config.manuscript_angle_tolerances_deg:
        decisions[manuscript_gate_id(angle)] = bool(
            abs(measurements["relative_length_change_a"])
            <= config.manuscript_length_tolerance
            and abs(measurements["relative_length_change_b"])
            <= config.manuscript_length_tolerance
            and measurements["absolute_angle_change_deg"] <= angle
        )
    return tuple(
        GateDecision(
            candidate_id=candidate.candidate_id,
            gate_id=gate_id,
            admitted=admitted,
            measurements=measurements,
            thresholds=_gate_thresholds(config, gate_id),
        )
        for gate_id, admitted in decisions.items()
    )


def build_boundary_candidates(config: GateDomainConfig) -> tuple[GateCandidate, ...]:
    """Construct analytic strain states spanning the exact gate boundary."""

    base_cells = {
        "square": column_basis_from_parameters(1.0, 1.0, 90.0),
        "hexagonal": column_basis_from_parameters(1.0, 1.0, 60.0),
        "oblique": column_basis_from_parameters(1.3, 0.9, 73.0),
    }
    epsilon = config.max_principal_strain
    inside = max(0.0, epsilon - config.boundary_inside_offset)
    outside = epsilon + config.boundary_outside_offset
    states = {
        "zero": (0.0, 0.0),
        "positive_uniaxial_boundary": (0.0, epsilon),
        "negative_uniaxial_boundary": (-epsilon, 0.0),
        "positive_isotropic_boundary": (epsilon, epsilon),
        "negative_isotropic_boundary": (-epsilon, -epsilon),
        "pure_shear_boundary": (-epsilon, epsilon),
        "positive_uniaxial_inside": (0.0, inside),
        "negative_uniaxial_inside": (-inside, 0.0),
        "pure_shear_inside": (-inside, inside),
        "positive_uniaxial_outside": (0.0, outside),
        "negative_uniaxial_outside": (-outside, 0.0),
        "pure_shear_outside": (-outside, outside),
    }
    axis_angles = (0.0, 17.0, 43.0)
    output: list[GateCandidate] = []
    for base_id, basis_a in base_cells.items():
        for state_id, (epsilon_1, epsilon_2) in states.items():
            for axis_angle in axis_angles:
                deformation = _principal_stretch_map(
                    epsilon_1,
                    epsilon_2,
                    axis_angle,
                )
                basis_b = deformation @ basis_a
                expected = tuple(sorted((float(epsilon_1), float(epsilon_2))))
                expected_admitted = max(abs(value) for value in expected) <= epsilon
                candidate_id = f"boundary:{base_id}:{state_id}:axis_{axis_angle:g}"
                output.append(
                    GateCandidate(
                        candidate_id=candidate_id,
                        population="analytic_boundary",
                        basis_A=tuple(
                            tuple(float(value) for value in row) for row in basis_a
                        ),
                        basis_B=tuple(
                            tuple(float(value) for value in row) for row in basis_b
                        ),
                        parameters={
                            "base_id": base_id,
                            "state_id": state_id,
                            "axis_angle_deg": float(axis_angle),
                            "prescribed_principal_strains": list(expected),
                            "expected_calm_admitted": expected_admitted,
                        },
                    )
                )
    return tuple(output)


def evaluate_boundary_suite(
    config: GateDomainConfig,
) -> tuple[
    tuple[GateCandidate, ...],
    tuple[GateDecision, ...],
    dict[str, Any],
]:
    """Measure analytic boundary candidates with CALM's production strain type."""

    # The import remains local so claim schemas and non-C1 commands stay usable
    # without importing CALM's scientific implementation.
    from calm.interface.matching._orchestrator import (
        _admitted_d_cell_for_scoring,
    )
    from calm.interface.types import AffineInvariantStrain2D

    candidates = build_boundary_candidates(config)
    decisions: list[GateDecision] = []
    failures: list[dict[str, Any]] = []
    maximum_measurement_error = 0.0
    for candidate in candidates:
        basis_a = np.asarray(candidate.basis_A, dtype=float)
        basis_b = np.asarray(candidate.basis_B, dtype=float)
        state = AffineInvariantStrain2D.from_grams(
            basis_a.T @ basis_a,
            basis_b.T @ basis_b,
        )
        measured = np.asarray(state.principal_strains, dtype=float)
        expected = np.asarray(
            candidate.parameters["prescribed_principal_strains"],
            dtype=float,
        )
        measurement_error = float(np.max(np.abs(measured - expected)))
        maximum_measurement_error = max(maximum_measurement_error, measurement_error)
        metric_tolerance = max(
            2.0 * config.boundary_outside_offset,
            10.0 * config.boundary_measurement_tolerance,
        )
        production_score = _admitted_d_cell_for_scoring(
            state,
            strain_limit=config.max_principal_strain,
            metric_tolerance=metric_tolerance,
        )
        actual_admitted = production_score is not None
        replica_admitted = bool(_calm_admitted(state.max_abs_principal_strain, config))
        expected_admitted = bool(candidate.parameters["expected_calm_admitted"])
        if (
            measurement_error > config.boundary_measurement_tolerance
            or actual_admitted != expected_admitted
            or replica_admitted != actual_admitted
        ):
            failures.append(
                {
                    "candidate_id": candidate.candidate_id,
                    "measurement_error": measurement_error,
                    "expected_principal_strains": expected.tolist(),
                    "measured_principal_strains": measured.tolist(),
                    "expected_admitted": expected_admitted,
                    "actual_admitted": actual_admitted,
                    "replica_admitted": replica_admitted,
                }
            )
        candidate_decisions = list(_single_gate_decisions(candidate, config))
        calm_index = next(
            index
            for index, decision in enumerate(candidate_decisions)
            if decision.gate_id == CALM_GATE_ID
        )
        calm_decision = candidate_decisions[calm_index]
        candidate_decisions[calm_index] = GateDecision(
            candidate_id=calm_decision.candidate_id,
            gate_id=calm_decision.gate_id,
            admitted=actual_admitted,
            measurements={
                **calm_decision.measurements,
                "production_principal_strain_1": float(measured[0]),
                "production_principal_strain_2": float(measured[1]),
                "production_max_abs_principal_strain": float(
                    state.max_abs_principal_strain
                ),
                "analytic_measurement_error": measurement_error,
                "expected_admitted": expected_admitted,
                "vectorized_replica_admitted": replica_admitted,
                "production_admission_score": (
                    None if production_score is None else float(production_score)
                ),
            },
            thresholds=calm_decision.thresholds,
        )
        decisions.extend(candidate_decisions)

    return (
        candidates,
        tuple(decisions),
        {
            "candidate_count": len(candidates),
            "failure_count": len(failures),
            "passed": not failures,
            "maximum_principal_strain_error": maximum_measurement_error,
            "measurement_tolerance": config.boundary_measurement_tolerance,
            "failures": failures,
        },
    )


def _reference_rows(config: GateDomainConfig) -> np.ndarray:
    return column_basis_from_parameters(
        config.reference_a,
        config.reference_b,
        config.reference_gamma_deg,
    ).T


def _trial_rows_from_perturbations(
    delta_a: np.ndarray,
    delta_b: np.ndarray,
    delta_gamma_deg: np.ndarray,
    config: GateDomainConfig,
) -> np.ndarray:
    a = config.reference_a * (1.0 + delta_a)
    b = config.reference_b * (1.0 + delta_b)
    gamma = np.radians(config.reference_gamma_deg + delta_gamma_deg)
    vectors = np.empty((len(a), 2, 2), dtype=float)
    vectors[:, 0, 0] = a
    vectors[:, 0, 1] = 0.0
    vectors[:, 1, 0] = b * np.cos(gamma)
    vectors[:, 1, 1] = b * np.sin(gamma)
    return vectors


def _principal_strains_for_trial_rows(
    trial_rows: np.ndarray,
    config: GateDomainConfig,
) -> np.ndarray:
    reference_basis = _reference_rows(config).T
    gram_a = reference_basis.T @ reference_basis
    eigenvalues, eigenvectors = np.linalg.eigh(0.5 * (gram_a + gram_a.T))
    inverse_sqrt = eigenvectors @ np.diag(1.0 / np.sqrt(eigenvalues)) @ eigenvectors.T
    gram_b = np.einsum("nik,njk->nij", trial_rows, trial_rows)
    relative = np.einsum("ij,njk,kl->nil", inverse_sqrt, gram_b, inverse_sqrt)
    relative = 0.5 * (relative + np.swapaxes(relative, 1, 2))
    trace = relative[:, 0, 0] + relative[:, 1, 1]
    discriminant = np.sqrt(
        np.maximum(
            0.0,
            (relative[:, 0, 0] - relative[:, 1, 1]) ** 2 + 4.0 * relative[:, 0, 1] ** 2,
        )
    )
    mu_1 = 0.5 * (trace - discriminant)
    mu_2 = 0.5 * (trace + discriminant)
    if np.any(mu_1 <= 0.0) or np.any(mu_2 <= 0.0):
        raise RuntimeError("generated trial population contains a non-SPD metric")
    return 0.5 * np.log(np.column_stack((mu_1, mu_2)))


def _gate_arrays(
    delta_a: np.ndarray,
    delta_b: np.ndarray,
    delta_gamma_deg: np.ndarray,
    trial_rows: np.ndarray,
    principal_strains: np.ndarray,
    config: GateDomainConfig,
) -> dict[str, np.ndarray]:
    maximum_strain = np.max(np.abs(principal_strains), axis=1)
    gates: dict[str, np.ndarray] = {
        CALM_GATE_ID: _calm_admitted(maximum_strain, config),
        PYMATGEN_NATIVE_UNIDIRECTIONAL_GATE_ID: pymatgen_native_gate_batch(
            _reference_rows(config),
            trial_rows,
            max_length_tol=config.pymatgen_max_length_tol,
            max_angle_tol=config.pymatgen_max_angle_tol,
            bidirectional=False,
        ),
        PYMATGEN_NATIVE_BIDIRECTIONAL_GATE_ID: pymatgen_native_gate_batch(
            _reference_rows(config),
            trial_rows,
            max_length_tol=config.pymatgen_max_length_tol,
            max_angle_tol=config.pymatgen_max_angle_tol,
            bidirectional=True,
        ),
    }
    for angle in config.manuscript_angle_tolerances_deg:
        gates[manuscript_gate_id(angle)] = (
            (np.abs(delta_a) <= config.manuscript_length_tolerance)
            & (np.abs(delta_b) <= config.manuscript_length_tolerance)
            & (np.abs(delta_gamma_deg) <= angle)
        )
    return gates


def _candidate_sample_row(
    index: int,
    delta_a: float,
    delta_b: float,
    delta_gamma_deg: float,
    principal_strains: np.ndarray,
    gate_arrays: Mapping[str, np.ndarray],
    local_index: int,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "schema": "calm.gate_candidate_sample/v1",
        "candidate_id": f"trial:{index:012d}",
        "sample_index": int(index),
        "delta_a_fraction": float(delta_a),
        "delta_b_fraction": float(delta_b),
        "delta_gamma_deg": float(delta_gamma_deg),
        "principal_strain_1": float(principal_strains[local_index, 0]),
        "principal_strain_2": float(principal_strains[local_index, 1]),
        "max_abs_principal_strain": float(
            np.max(np.abs(principal_strains[local_index]))
        ),
    }
    for gate_id, values in gate_arrays.items():
        row[gate_id] = bool(values[local_index])
    return row


def _decision_sample_rows(
    candidate_rows: Sequence[Mapping[str, Any]],
    config: GateDomainConfig,
) -> list[dict[str, Any]]:
    gate_ids = tuple(_gate_labels(config))
    output: list[dict[str, Any]] = []
    for candidate in candidate_rows:
        for gate_id in gate_ids:
            output.append(
                {
                    "schema": "calm.gate_decision_sample/v1",
                    "candidate_id": candidate["candidate_id"],
                    "gate_id": gate_id,
                    "admitted": bool(candidate[gate_id]),
                }
            )
    return output


def _disagreement_example_rows(
    *,
    global_start: int,
    delta_a: np.ndarray,
    delta_b: np.ndarray,
    delta_gamma_deg: np.ndarray,
    principal_strains: np.ndarray,
    gates: Mapping[str, np.ndarray],
    remaining: dict[tuple[str, str], int],
) -> list[dict[str, Any]]:
    calm = gates[CALM_GATE_ID]
    output: list[dict[str, Any]] = []
    for gate_id, values in gates.items():
        if gate_id == CALM_GATE_ID:
            continue
        categories = {
            "calm_only": calm & ~values,
            "comparison_gate_only": ~calm & values,
        }
        for category, mask in categories.items():
            key = (gate_id, category)
            capacity = remaining.get(key, 0)
            if capacity <= 0:
                continue
            local_indices = np.flatnonzero(mask)[:capacity]
            for local_index in local_indices:
                output.append(
                    {
                        "schema": GATE_EXAMPLE_SCHEMA,
                        "candidate_id": f"trial:{global_start + int(local_index):012d}",
                        "sample_index": global_start + int(local_index),
                        "comparison_gate_id": gate_id,
                        "category": category,
                        "delta_a_fraction": float(delta_a[local_index]),
                        "delta_b_fraction": float(delta_b[local_index]),
                        "delta_gamma_deg": float(delta_gamma_deg[local_index]),
                        "principal_strain_1": float(principal_strains[local_index, 0]),
                        "principal_strain_2": float(principal_strains[local_index, 1]),
                        "max_abs_principal_strain": float(
                            np.max(np.abs(principal_strains[local_index]))
                        ),
                        "calm_admitted": bool(calm[local_index]),
                        "comparison_gate_admitted": bool(values[local_index]),
                    }
                )
            remaining[key] = capacity - len(local_indices)
    return output


def _pymatgen_parity_probe(
    candidate_rows: Sequence[Mapping[str, Any]],
    config: GateDomainConfig,
) -> dict[str, Any]:
    """Optionally compare the replica with an installed pymatgen implementation."""

    try:
        from pymatgen.analysis.interfaces.zsl import is_same_vectors
    except (ImportError, ModuleNotFoundError):
        return {
            "status": "not_available",
            "pymatgen_version": None,
            "probe_count": 0,
            "mismatch_count": 0,
        }

    try:
        version = importlib.metadata.version("pymatgen")
    except importlib.metadata.PackageNotFoundError:
        version = "unknown"
    reference = reduce_vectors_batch(_reference_rows(config)[np.newaxis, :, :])[0]
    mismatches: list[dict[str, Any]] = []
    for row in candidate_rows[: min(128, len(candidate_rows))]:
        trial = _trial_rows_from_perturbations(
            np.asarray([row["delta_a_fraction"]]),
            np.asarray([row["delta_b_fraction"]]),
            np.asarray([row["delta_gamma_deg"]]),
            config,
        )
        reduced = reduce_vectors_batch(trial)[0]
        for bidirectional, gate_id in (
            (False, PYMATGEN_NATIVE_UNIDIRECTIONAL_GATE_ID),
            (True, PYMATGEN_NATIVE_BIDIRECTIONAL_GATE_ID),
        ):
            actual = bool(
                is_same_vectors(
                    np.pad(reference, ((0, 0), (0, 1))),
                    np.pad(reduced, ((0, 0), (0, 1))),
                    bidirectional=bidirectional,
                    max_length_tol=config.pymatgen_max_length_tol,
                    max_angle_tol=config.pymatgen_max_angle_tol,
                )
            )
            expected = bool(row[gate_id])
            if actual != expected:
                mismatches.append(
                    {
                        "candidate_id": row["candidate_id"],
                        "gate_id": gate_id,
                        "replica": expected,
                        "installed_pymatgen": actual,
                    }
                )
    return {
        "status": "pass" if not mismatches else "fail",
        "pymatgen_version": version,
        "probe_count": min(128, len(candidate_rows)) * 2,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
    }


def _histogram_edges(config: GateDomainConfig) -> np.ndarray:
    return np.linspace(
        config.histogram_min_strain,
        config.histogram_max_strain,
        config.histogram_bin_count + 1,
        dtype=float,
    )


def _empty_histogram_counts(config: GateDomainConfig) -> dict[str, np.ndarray]:
    shape = (config.histogram_bin_count, config.histogram_bin_count)
    return {
        population_id: np.zeros(shape, dtype=np.int64)
        for population_id in histogram_population_ids(config)
    }


def _histogram_masks(
    gates: Mapping[str, np.ndarray],
    config: GateDomainConfig,
) -> dict[str, np.ndarray]:
    calm = np.asarray(gates[CALM_GATE_ID], dtype=bool)
    masks = {TARGET_POPULATION_ID: calm}
    for angle in config.manuscript_angle_tolerances_deg:
        gate_id = manuscript_gate_id(angle)
        masks[gate_id] = np.asarray(gates[gate_id], dtype=bool)
    return masks


def _update_histograms(
    *,
    principal_strains: np.ndarray,
    masks: Mapping[str, np.ndarray],
    edges: np.ndarray,
    counts: Mapping[str, np.ndarray],
    totals: dict[str, int],
    out_of_range: dict[str, int],
) -> None:
    bin_count = len(edges) - 1
    epsilon_1 = np.asarray(principal_strains[:, 0], dtype=float)
    epsilon_2 = np.asarray(principal_strains[:, 1], dtype=float)
    valid = (
        (epsilon_1 >= edges[0])
        & (epsilon_1 <= edges[-1])
        & (epsilon_2 >= edges[0])
        & (epsilon_2 <= edges[-1])
    )
    bin_i = np.searchsorted(edges, epsilon_1, side="right") - 1
    bin_j = np.searchsorted(edges, epsilon_2, side="right") - 1
    bin_i = np.minimum(bin_i, bin_count - 1)
    bin_j = np.minimum(bin_j, bin_count - 1)
    flat_indices = bin_i * bin_count + bin_j

    for population_id, raw_mask in masks.items():
        mask = np.asarray(raw_mask, dtype=bool)
        if mask.shape != valid.shape:
            raise ValueError("histogram masks must match the strain-array length")
        totals[population_id] += int(np.count_nonzero(mask))
        outside = mask & ~valid
        out_of_range[population_id] += int(np.count_nonzero(outside))
        selected = mask & valid
        increment = np.bincount(
            flat_indices[selected],
            minlength=bin_count * bin_count,
        ).reshape((bin_count, bin_count))
        counts[population_id] += increment.astype(np.int64, copy=False)


def _histogram_summary_rows(
    *,
    config: GateDomainConfig,
    counts: Mapping[str, np.ndarray],
    totals: Mapping[str, int],
    out_of_range: Mapping[str, int],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for population_id in histogram_population_ids(config):
        histogram_total = int(np.sum(counts[population_id], dtype=np.int64))
        outside = int(out_of_range[population_id])
        total = int(totals[population_id])
        if histogram_total + outside != total:
            raise RuntimeError(
                f"histogram accounting failed for population {population_id!r}"
            )
        rows.append(
            {
                "schema": GATE_HISTOGRAM_SUMMARY_SCHEMA,
                "population_id": population_id,
                "population_label": histogram_population_label(
                    config,
                    population_id,
                ),
                "histogram_file": histogram_population_filename(
                    config,
                    population_id,
                ),
                "total_count": total,
                "in_range_count": histogram_total,
                "out_of_range_count": outside,
                "nonzero_bin_count": int(np.count_nonzero(counts[population_id])),
            }
        )
    return rows


def evaluate_trial_population(config: GateDomainConfig) -> dict[str, Any]:
    """Stream the seeded common candidate population and aggregate gate evidence."""

    gate_labels = _gate_labels(config)
    counts = {gate_id: _ConfusionCounts() for gate_id in gate_labels}
    convergence_rows: list[dict[str, Any]] = []
    candidate_sample: list[dict[str, Any]] = []
    disagreement_examples: list[dict[str, Any]] = []
    remaining_examples = {
        (gate_id, category): config.disagreement_examples_per_category
        for gate_id in gate_labels
        if gate_id != CALM_GATE_ID
        for category in ("calm_only", "comparison_gate_only")
    }
    histogram_edges = _histogram_edges(config)
    histogram_counts = _empty_histogram_counts(config)
    histogram_totals = {
        population_id: 0 for population_id in histogram_population_ids(config)
    }
    histogram_out_of_range = {
        population_id: 0 for population_id in histogram_population_ids(config)
    }
    rng = np.random.Generator(np.random.PCG64(config.seed))
    processed = 0

    for checkpoint in config.effective_checkpoints:
        while processed < checkpoint:
            size = min(config.chunk_size, checkpoint - processed)
            unit = rng.random((size, 3))
            delta_a = (
                -config.maximum_length_perturbation
                + 2.0 * config.maximum_length_perturbation * unit[:, 0]
            )
            delta_b = (
                -config.maximum_length_perturbation
                + 2.0 * config.maximum_length_perturbation * unit[:, 1]
            )
            delta_gamma = (
                -config.maximum_angle_perturbation_deg
                + 2.0 * config.maximum_angle_perturbation_deg * unit[:, 2]
            )
            trial_rows = _trial_rows_from_perturbations(
                delta_a,
                delta_b,
                delta_gamma,
                config,
            )
            principal_strains = _principal_strains_for_trial_rows(
                trial_rows,
                config,
            )
            gates = _gate_arrays(
                delta_a,
                delta_b,
                delta_gamma,
                trial_rows,
                principal_strains,
                config,
            )
            calm = gates[CALM_GATE_ID]
            for gate_id, values in gates.items():
                counts[gate_id].update(calm, values)
            _update_histograms(
                principal_strains=principal_strains,
                masks=_histogram_masks(gates, config),
                edges=histogram_edges,
                counts=histogram_counts,
                totals=histogram_totals,
                out_of_range=histogram_out_of_range,
            )

            sample_capacity = config.retained_sample_count - len(candidate_sample)
            if sample_capacity > 0:
                for local_index in range(min(size, sample_capacity)):
                    candidate_sample.append(
                        _candidate_sample_row(
                            processed + local_index,
                            delta_a[local_index],
                            delta_b[local_index],
                            delta_gamma[local_index],
                            principal_strains,
                            gates,
                            local_index,
                        )
                    )
            disagreement_examples.extend(
                _disagreement_example_rows(
                    global_start=processed,
                    delta_a=delta_a,
                    delta_b=delta_b,
                    delta_gamma_deg=delta_gamma,
                    principal_strains=principal_strains,
                    gates=gates,
                    remaining=remaining_examples,
                )
            )
            processed += size

        for gate_id, counter in counts.items():
            convergence_rows.append(
                {
                    "schema": GATE_CONVERGENCE_SCHEMA,
                    "sample_count": checkpoint,
                    "gate_id": gate_id,
                    "gate_label": gate_labels[gate_id],
                    **counter.to_metrics(),
                }
            )

    final_rows = []
    for gate_id, counter in counts.items():
        final_rows.append(
            {
                "schema": GATE_CONFUSION_SCHEMA,
                "gate_id": gate_id,
                "gate_label": gate_labels[gate_id],
                **counter.to_metrics(),
            }
        )
    disagreement_examples.sort(
        key=lambda row: (
            str(row["comparison_gate_id"]),
            str(row["category"]),
            int(row["sample_index"]),
        )
    )
    histogram_counts[CALM_GATE_ID] = histogram_counts[TARGET_POPULATION_ID].copy()
    histogram_totals[CALM_GATE_ID] = histogram_totals[TARGET_POPULATION_ID]
    histogram_out_of_range[CALM_GATE_ID] = histogram_out_of_range[TARGET_POPULATION_ID]
    histogram_summary_rows = _histogram_summary_rows(
        config=config,
        counts=histogram_counts,
        totals=histogram_totals,
        out_of_range=histogram_out_of_range,
    )
    return {
        "confusion_rows": final_rows,
        "convergence_rows": convergence_rows,
        "candidate_sample_rows": candidate_sample,
        "decision_sample_rows": _decision_sample_rows(candidate_sample, config),
        "disagreement_example_rows": disagreement_examples,
        "pymatgen_parity": _pymatgen_parity_probe(candidate_sample, config),
        "histogram_edges": histogram_edges,
        "histogram_counts": histogram_counts,
        "histogram_summary_rows": histogram_summary_rows,
    }


def _boundary_candidate_csv_rows(
    candidates: Sequence[GateCandidate],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for candidate in candidates:
        parameters = candidate.parameters
        expected = parameters["prescribed_principal_strains"]
        rows.append(
            {
                "schema": candidate.schema,
                "candidate_id": candidate.candidate_id,
                "population": candidate.population,
                "base_id": parameters["base_id"],
                "state_id": parameters["state_id"],
                "axis_angle_deg": parameters["axis_angle_deg"],
                "expected_principal_strain_1": expected[0],
                "expected_principal_strain_2": expected[1],
                "expected_calm_admitted": parameters["expected_calm_admitted"],
                "basis_A": repr(candidate.basis_A),
                "basis_B": repr(candidate.basis_B),
            }
        )
    return rows


def _boundary_decision_csv_rows(
    decisions: Sequence[GateDecision],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for decision in decisions:
        measurements = decision.measurements
        rows.append(
            {
                "schema": decision.schema,
                "candidate_id": decision.candidate_id,
                "gate_id": decision.gate_id,
                "admitted": decision.admitted,
                "principal_strain_1": measurements.get("principal_strain_1"),
                "principal_strain_2": measurements.get("principal_strain_2"),
                "max_abs_principal_strain": measurements.get(
                    "max_abs_principal_strain"
                ),
                "production_principal_strain_1": measurements.get(
                    "production_principal_strain_1"
                ),
                "production_principal_strain_2": measurements.get(
                    "production_principal_strain_2"
                ),
                "analytic_measurement_error": measurements.get(
                    "analytic_measurement_error"
                ),
                "expected_admitted": measurements.get("expected_admitted"),
                "relative_length_change_a": measurements.get(
                    "relative_length_change_a"
                ),
                "relative_length_change_b": measurements.get(
                    "relative_length_change_b"
                ),
                "absolute_angle_change_deg": measurements.get(
                    "absolute_angle_change_deg"
                ),
                "thresholds": repr(decision.thresholds),
            }
        )
    return rows


def _csv_fieldnames(rows: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    if not rows:
        raise ValueError("cannot infer fieldnames from empty rows")
    ordered: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                ordered.append(key)
    return tuple(ordered)


def _histogram_edge_rows(edges: np.ndarray) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for axis in ("epsilon_1", "epsilon_2"):
        for edge_index, edge_value in enumerate(edges):
            rows.append(
                {
                    "schema": GATE_HISTOGRAM_EDGE_SCHEMA,
                    "axis": axis,
                    "edge_index": int(edge_index),
                    "edge_value": float(edge_value),
                }
            )
    return rows


def _histogram_count_rows(
    *,
    population_id: str,
    counts: np.ndarray,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for bin_i in range(counts.shape[0]):
        for bin_j in range(counts.shape[1]):
            rows.append(
                {
                    "schema": GATE_HISTOGRAM_SCHEMA,
                    "population_id": population_id,
                    "bin_i": int(bin_i),
                    "bin_j": int(bin_j),
                    "count": int(counts[bin_i, bin_j]),
                }
            )
    return rows


def run_gate_domain_qualification(
    *,
    output_root: str | Path,
    repository_root: str | Path,
    command: Sequence[str],
    config: GateDomainConfig,
) -> GateDomainArtifacts:
    """Execute C1 qualification and common-domain gate characterization."""

    root = Path(output_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)

    boundary_candidates, boundary_decisions, boundary_summary = evaluate_boundary_suite(
        config
    )
    trial_evidence = evaluate_trial_population(config)
    out_of_range_rows = [
        row
        for row in trial_evidence["histogram_summary_rows"]
        if int(row["out_of_range_count"]) != 0
    ]
    if out_of_range_rows:
        details = ", ".join(
            f"{row['population_id']}={row['out_of_range_count']}"
            for row in out_of_range_rows
        )
        raise RuntimeError(
            f"principal-strain histogram bounds excluded accepted candidates: {details}"
        )

    boundary_candidate_rows = _boundary_candidate_csv_rows(boundary_candidates)
    boundary_decision_rows = _boundary_decision_csv_rows(boundary_decisions)
    boundary_candidates_path = write_csv_atomic(
        root / "gate_boundary_candidates.csv",
        boundary_candidate_rows,
        fieldnames=_csv_fieldnames(boundary_candidate_rows),
    )
    boundary_decisions_path = write_csv_atomic(
        root / "gate_boundary_decisions.csv",
        boundary_decision_rows,
        fieldnames=_csv_fieldnames(boundary_decision_rows),
    )
    confusion_path = write_csv_atomic(
        root / "gate_confusion_matrix.csv",
        trial_evidence["confusion_rows"],
        fieldnames=_csv_fieldnames(trial_evidence["confusion_rows"]),
    )
    convergence_path = write_csv_atomic(
        root / "gate_convergence.csv",
        trial_evidence["convergence_rows"],
        fieldnames=_csv_fieldnames(trial_evidence["convergence_rows"]),
    )
    candidate_sample_fields = (
        "schema",
        "candidate_id",
        "sample_index",
        "delta_a_fraction",
        "delta_b_fraction",
        "delta_gamma_deg",
        "principal_strain_1",
        "principal_strain_2",
        "max_abs_principal_strain",
        *_gate_labels(config).keys(),
    )
    candidate_sample_path = write_csv_atomic(
        root / "gate_candidate_sample.csv",
        trial_evidence["candidate_sample_rows"],
        fieldnames=candidate_sample_fields,
    )
    decision_sample_path = write_csv_atomic(
        root / "gate_decision_sample.csv",
        trial_evidence["decision_sample_rows"],
        fieldnames=("schema", "candidate_id", "gate_id", "admitted"),
    )
    disagreement_path = write_csv_atomic(
        root / "gate_disagreement_examples.csv",
        trial_evidence["disagreement_example_rows"],
        fieldnames=(
            "schema",
            "candidate_id",
            "sample_index",
            "comparison_gate_id",
            "category",
            "delta_a_fraction",
            "delta_b_fraction",
            "delta_gamma_deg",
            "principal_strain_1",
            "principal_strain_2",
            "max_abs_principal_strain",
            "calm_admitted",
            "comparison_gate_admitted",
        ),
    )
    histogram_edges_path = write_csv_atomic(
        root / "principal_strain_histogram_bin_edges.csv",
        _histogram_edge_rows(trial_evidence["histogram_edges"]),
        fieldnames=("schema", "axis", "edge_index", "edge_value"),
    )
    histogram_summary_path = write_csv_atomic(
        root / "principal_strain_histogram_summary.csv",
        trial_evidence["histogram_summary_rows"],
        fieldnames=(
            "schema",
            "population_id",
            "population_label",
            "histogram_file",
            "total_count",
            "in_range_count",
            "out_of_range_count",
            "nonzero_bin_count",
        ),
    )
    histogram_paths: list[Path] = []
    for population_id in histogram_population_ids(config):
        path = write_csv_atomic(
            root / histogram_population_filename(config, population_id),
            _histogram_count_rows(
                population_id=population_id,
                counts=trial_evidence["histogram_counts"][population_id],
            ),
            fieldnames=("schema", "population_id", "bin_i", "bin_j", "count"),
        )
        histogram_paths.append(path)

    c1_passed = bool(boundary_summary["passed"])
    status = ClaimStatus.PASS if c1_passed else ClaimStatus.FAIL
    evidence_names = (
        boundary_candidates_path.name,
        boundary_decisions_path.name,
        confusion_path.name,
        convergence_path.name,
        histogram_edges_path.name,
        histogram_summary_path.name,
        *(path.name for path in histogram_paths),
    )
    result = ClaimResult(
        claim_id=ClaimId.C1_STRAIN_DOMAIN,
        status=status,
        summary=(
            "Analytic boundary states agree with CALM's production affine-"
            "invariant principal-strain calculation and strict admission domain."
            if c1_passed
            else "One or more analytic boundary states disagree with CALM's "
            "principal-strain calculation or admission domain."
        ),
        evidence_files=evidence_names,
        metrics={
            "boundary_candidate_count": boundary_summary["candidate_count"],
            "boundary_failure_count": boundary_summary["failure_count"],
            "maximum_principal_strain_error": boundary_summary[
                "maximum_principal_strain_error"
            ],
            "trial_sample_count": config.sample_count,
            "histogram_bin_count_per_axis": config.histogram_bin_count,
            "histogram_out_of_range_count": 0,
        },
        notes=(
            "The reduced-parameter and pymatgen-native rows are descriptive "
            "common-domain comparisons; they do not complete claim C7.",
            "The pymatgen area-ratio transformation-set prefilter is outside "
            "this vector-gate experiment.",
        ),
    )
    claim_result_path = write_json_atomic(root / "claim_result.json", result.to_dict())

    summary_payload = {
        "schema": GATE_DOMAIN_SUMMARY_SCHEMA,
        "suite_version": "claims_v1",
        "claim_results": {ClaimId.C1_STRAIN_DOMAIN.value: result.to_dict()},
        "informative_for_incomplete_claims": [ClaimId.C7_ZSL_COMPARISON.value],
        "config": config.to_dict(),
        "boundary_suite": boundary_summary,
        "trial_population": {
            "sample_count": config.sample_count,
            "seed": config.seed,
            "confusion_matrix": trial_evidence["confusion_rows"],
            "pymatgen_native_replica_parity": trial_evidence["pymatgen_parity"],
            "retained_candidate_sample_count": len(
                trial_evidence["candidate_sample_rows"]
            ),
            "retained_disagreement_example_count": len(
                trial_evidence["disagreement_example_rows"]
            ),
            "principal_strain_histograms": {
                "bin_edges_file": histogram_edges_path.name,
                "summary_file": histogram_summary_path.name,
                "population_files": [path.name for path in histogram_paths],
                "populations": trial_evidence["histogram_summary_rows"],
            },
        },
        "interpretation": {
            "c1_pass_fail_basis": (
                "analytic strain reconstruction and exact boundary admission"
            ),
            "c7_status": "not_complete",
            "pymatgen_native_scope": (
                "reduce_vectors plus is_same_vectors length/angle predicate only"
            ),
            "legacy_suite_modified": False,
        },
    }
    summary_path = write_json_atomic(root / "gate_domain_summary.json", summary_payload)

    artifacts = tuple(
        artifact_record(path, relative_to=root, media_type=media_type)
        for path, media_type in (
            (claim_result_path, "application/json"),
            (summary_path, "application/json"),
            (boundary_candidates_path, "text/csv"),
            (boundary_decisions_path, "text/csv"),
            (confusion_path, "text/csv"),
            (convergence_path, "text/csv"),
            (candidate_sample_path, "text/csv"),
            (decision_sample_path, "text/csv"),
            (disagreement_path, "text/csv"),
            (histogram_edges_path, "text/csv"),
            (histogram_summary_path, "text/csv"),
            *((path, "text/csv") for path in histogram_paths),
        )
    )
    config_payload = config.to_dict()
    manifest = build_manifest(
        repository_root=repository_root,
        output_root=root,
        command=command,
        selected_claims=(ClaimId.C1_STRAIN_DOMAIN,),
        artifacts=artifacts,
        fixture_hashes={
            "gate_domain_config": sha256_bytes(canonical_json_bytes(config_payload)),
        },
        policy_settings={
            "gate_domain": config_payload,
            "calm_admission_contract": {
                "source_contract": (
                    "calm.interface.matching._orchestrator._admitted_d_cell_for_scoring"
                ),
                "vectorized_replica_version": 1,
            },
            "pymatgen_native_replica": {
                "source_contract": (
                    "pymatgen.analysis.interfaces.zsl.reduce_vectors+is_same_vectors"
                ),
                "replica_version": 1,
            },
        },
        seeds={"trial_population": config.seed},
    )
    manifest_path = write_json_atomic(
        root / "benchmark_manifest.json", manifest.to_dict()
    )

    return GateDomainArtifacts(
        manifest=manifest_path,
        claim_result=claim_result_path,
        summary=summary_path,
        boundary_candidates=boundary_candidates_path,
        boundary_decisions=boundary_decisions_path,
        confusion_matrix=confusion_path,
        convergence=convergence_path,
        candidate_sample=candidate_sample_path,
        decision_sample=decision_sample_path,
        disagreement_examples=disagreement_path,
        histogram_bin_edges=histogram_edges_path,
        histogram_summary=histogram_summary_path,
        histogram_files=tuple(histogram_paths),
        result=result,
    )


def parse_checkpoints(value: str) -> tuple[int, ...]:
    checkpoints = tuple(
        sorted({int(token.strip()) for token in value.split(",") if token.strip()})
    )
    if not checkpoints or any(checkpoint <= 0 for checkpoint in checkpoints):
        raise ValueError(
            "checkpoints must be a comma-separated list of positive integers"
        )
    return checkpoints


def standalone_command(argv: Sequence[str]) -> tuple[str, ...]:
    return (
        sys.executable,
        "-m",
        "benchmarks.run_gate_domain_qualification",
        *tuple(argv),
    )


__all__ = [
    "CALM_GATE_ID",
    "DEFAULT_CHECKPOINTS",
    "DEFAULT_CHUNK_SIZE",
    "DEFAULT_HISTOGRAM_BIN_COUNT",
    "DEFAULT_HISTOGRAM_MAX_STRAIN",
    "DEFAULT_HISTOGRAM_MIN_STRAIN",
    "DEFAULT_SAMPLE_COUNT",
    "DEFAULT_SEED",
    "GATE_CONFUSION_SCHEMA",
    "GATE_CONVERGENCE_SCHEMA",
    "GATE_DOMAIN_SUMMARY_SCHEMA",
    "GATE_HISTOGRAM_EDGE_SCHEMA",
    "GATE_HISTOGRAM_SCHEMA",
    "GATE_HISTOGRAM_SUMMARY_SCHEMA",
    "GateDomainArtifacts",
    "GateDomainConfig",
    "TARGET_POPULATION_ID",
    "build_boundary_candidates",
    "column_basis_from_parameters",
    "evaluate_boundary_suite",
    "evaluate_trial_population",
    "histogram_population_filename",
    "histogram_population_ids",
    "histogram_population_label",
    "manuscript_gate_id",
    "parse_checkpoints",
    "pymatgen_native_gate_batch",
    "reduce_vectors_batch",
    "run_gate_domain_qualification",
    "standalone_command",
]
